import logging
from io import StringIO

from mako.runtime import Context
from mako.template import Template

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.depends("product_variant_ids.product_tmpl_id")
    def _compute_product_variant_count(self):
        """For configurable products return the number of variants configured or
        1 as many views and methods trigger only when a template has at least
        one variant attached. Since we create them from the template we should
        have access to them always"""
        result = super()._compute_product_variant_count()
        for product_tmpl in self:
            config_ok = product_tmpl.config_ok
            variant_count = product_tmpl.product_variant_count
            if config_ok and not variant_count:
                product_tmpl.product_variant_count = 1
        return result

    @api.depends("attribute_line_ids.value_ids")
    def _compute_template_attr_vals(self):
        """Compute all attribute values added in attribute line on
        product template"""
        for product_tmpl in self:
            if product_tmpl.config_ok:
                value_ids = product_tmpl.attribute_line_ids.mapped("value_ids")
                product_tmpl.attribute_line_val_ids = value_ids
            else:
                product_tmpl.attribute_line_val_ids = False

    @api.constrains("attribute_line_ids", "attribute_value_line_ids")
    def check_attr_value_ids(self):
        """Check attribute lines don't have some attribute value that
        is not present in attribute lines of that product template"""
        for product_tmpl in self:
            if not product_tmpl.env.context.get("check_constraint", True):
                continue
            attr_val_lines = product_tmpl.attribute_value_line_ids
            attr_val_ids = attr_val_lines.mapped("value_ids")
            if not attr_val_ids <= product_tmpl.attribute_line_val_ids:
                raise ValidationError(
                    self.env._(
                        "All attribute values used in attribute value lines "
                        "must be defined in the attribute lines of the "
                        "template"
                    )
                )

    @api.constrains("attribute_value_line_ids")
    def _validate_unique_config(self):
        """Check for duplicate configurations for the same
        attribute value in image lines"""
        for template in self:
            attr_val_line_vals = template.attribute_value_line_ids.read(
                ["value_id", "value_ids"], load=False
            )
            attr_val_line_vals = [
                (line["value_id"], tuple(line["value_ids"]))
                for line in attr_val_line_vals
            ]
            if len(set(attr_val_line_vals)) != len(attr_val_line_vals):
                raise ValidationError(
                    self.env._(
                        "You cannot have a duplicate configuration for the same value"
                    )
                )

    config_ok = fields.Boolean(string="Can be Configured")

    # ─ L'ONGLET A SON PROPRE CHAMP SUR LES MÊMES LIGNES — D-209 ─────────────
    #
    # ⚠️ **UN MÊME `One2many` DÉCLARÉ DEUX FOIS DANS UN FORMULAIRE CASSE LA
    # SAUVEGARDE.** Mesuré : l'onglet configurateur montrant `attribute_line_ids`
    # à côté de l'onglet « Attributs & Variantes » qui le montre déjà,
    # l'enregistrement d'un produit levait *« Values must belong to the attribute
    # of the corresponding attribute_line »* — deux jeux de commandes pour les
    # mêmes lignes, envoyés dans un ordre que rien ne garantit.
    #
    # ⓘ Un second champ, MÊME modèle et MÊME inverse : ce sont exactement les
    # mêmes enregistrements, donc le même ordre (Q2, *« un seul ordre partagé »*),
    # mais deux affichages indépendants. C'est ce qui permet à l'onglet
    # « Attributs & Variantes » de ne pas changer — correction de Gerry.
    configurator_line_ids = fields.One2many(
        comodel_name="product.template.attribute.line",
        inverse_name="product_tmpl_id",
        string="Configurator Attributes",
        help="The same attribute lines as the Attributes tab, shown with what "
             "the configurator needs: conditions, steps, 3D view.",
    )

    # ─ L'ARBRE DU CONFIGURATEUR, TEL QUE L'ÉCRAN LE LIT — D-210 ─────────────
    #
    # Maquette de Gerry : un arbre où l'étape est un bandeau, l'attribut une
    # ligne, et ses valeurs des lignes indentées portant chacune leur condition.
    #
    # ⚠️ **UNE LISTE ODOO NE SAIT NI S'IMBRIQUER NI MÊLER DEUX MODÈLES.** L'arbre
    # tient trois natures de lignes — étape, attribut, valeur — venues de trois
    # modèles. D'où un composant, et d'où cette méthode : le composant lit UNE
    # structure, au lieu de recomposer côté client une jointure que le serveur
    # fait mieux.
    #
    # ⚠️ **L'ÉTAPE EST UN BANDEAU RENDU, PAS UN ENREGISTREMENT DE PLUS.** Le
    # modèle n'a pas changé (D-202) : l'étape reste un marqueur porté par la ligne
    # qui l'ouvre. C'est l'affichage qui en tire un bandeau — ce qui est
    # exactement ce que la forme (A) promettait, *« le bandeau pourra venir plus
    # tard sans toucher au modèle »*.
    def get_configurator_tree(self):
        """L'arbre à afficher — étapes, attributs, valeurs, conditions.

        ⓘ Rendu dans l'ORDRE des lignes d'attribut : c'est lui qui porte
        l'appartenance aux étapes, et c'est le même que celui de l'onglet
        « Attributs & Variantes » (Q2).
        """
        self.ensure_one()
        lignes = []
        ouverte = False
        # Les conditions POSÉES SUR DES VALEURS vivent sur un autre modèle : on
        # les rassemble en une passe plutôt qu'une requête par valeur.
        conditions_valeur = {}
        for regle in self.config_line_ids:
            for valeur in regle.value_ids:
                conditions_valeur.setdefault(
                    (regle.attribute_line_id.id, valeur.id), regle
                )

        for ligne in self.attribute_line_ids.sorted():
            if ligne.config_step_id and ligne.config_step_id != ouverte:
                ouverte = ligne.config_step_id
                lignes.append({
                    "kind": "step",
                    "id": ligne.config_step_id.id,
                    "line_id": ligne.id,
                    "name": ligne.config_step_id.display_name,
                })
            lignes.append({
                "kind": "attribute",
                "id": ligne.id,
                "name": ligne.attribute_id.display_name,
                "facets": ligne.visibility_domain_id._facet_data(),
                "domain_id": ligne.visibility_domain_id.id,
                "camera": ligne._configurator_camera_name(),
                "values": [
                    {
                        "kind": "value",
                        "id": valeur.id,
                        "line_id": ligne.id,
                        "name": valeur.name,
                        "facets": conditions_valeur.get(
                            (ligne.id, valeur.id),
                            self.env["product.config.line"],
                        ).domain_id._facet_data(),
                    }
                    for valeur in ligne.value_ids
                ],
            })
        return lignes

    # ─ CE QUE L'ARBRE PEUT FAIRE — D-211 ────────────────────────────────────
    #
    # ⚠️ **LES GESTES VIVENT ICI, PAS DANS LE COMPOSANT.** Chacun décide quelque
    # chose — ce qu'une corbeille détruit, ce qu'un « × » retire — et ces
    # décisions doivent tenir quelle que soit l'interface. Un composant qui
    # écrirait directement les mettrait hors de portée des tests et des imports.

    def configurator_remove_facet(self, domain_line_id):
        """Retire UNE règle d'une condition, comme le « × » d'une pastille.

        ⚠️ Une règle, pas la condition entière : une condition à trois règles se
        perdrait pour en corriger une. ⓘ Et la condition VIDE reste en place —
        elle porte un nom, elle est peut-être partagée, et la supprimer parce
        qu'on a retiré sa dernière règle serait décider à la place de
        l'utilisateur.
        """
        self.ensure_one()
        self.env["product.config.domain.line"].browse(domain_line_id).unlink()
        return True

    def configurator_remove_value(self, line_id, value_id):
        """Retire une valeur de l'attribut, sur CE produit.

        ⓘ On écrit sur `value_ids` de la ligne : c'est le chemin ordinaire, donc
        celui qui déclenche la règle des deux visages — supprimer si possible,
        désactiver sinon (D-205). Détruire la valeur du produit directement
        court-circuiterait ce filet.
        """
        self.ensure_one()
        ligne = self.env["product.template.attribute.line"].browse(line_id)
        ligne.value_ids = [(3, value_id)]
        return True

    def configurator_clear_step(self, line_id):
        """L'étape cesse d'exister à cet endroit — le marqueur s'efface.

        ⚠️ Ce n'est pas une suppression d'étape : l'étape est un enregistrement
        partagé entre produits (`product.config.step`). On retire le MARQUEUR, et
        ce qui suivait rejoint l'étape précédente — ou aucune. C'est la
        contrepartie du séparateur, et elle est visible tout de suite.
        """
        self.ensure_one()
        self.env["product.template.attribute.line"].browse(line_id).config_step_id = False
        return True

    def configurator_open_condition(self, line_id, value_id=False):
        """Ouvre — et crée au besoin — la condition d'une ligne ou d'une valeur.

        ⚠️ **SANS CECI, RETIRER « Configuration Restrictions » PERDRAIT UNE
        CAPACITÉ.** C'était le seul endroit d'où l'on crée une condition PAR
        VALEUR : l'arbre les affichait sans pouvoir en poser une. Question de
        Gerry — *« Configuration Restrictions n'a plus d'utilité ? »* — et la
        réponse était « si, jusqu'à ce que l'arbre sache le faire ».

        ⚠️ **LA CONDITION EST CRÉÉE AU CLIC**, parce qu'elle EST le lien : on ne
        peut pas ouvrir l'éditeur de quelque chose qui n'existe pas, et rattacher
        après coup demanderait un rappel que l'action ne fournit pas. ⓘ Une
        condition restée vide n'est pas un déchet : D-211 a déjà décidé qu'on ne
        supprime pas une condition parce qu'elle n'a plus de règle — elle porte un
        nom et peut être partagée.
        """
        self.ensure_one()
        ligne = self.env["product.template.attribute.line"].browse(line_id)
        if value_id:
            valeur = self.env["product.attribute.value"].browse(value_id)
            regle = self.config_line_ids.filtered(
                lambda r: r.attribute_line_id == ligne and valeur in r.value_ids
            )[:1]
            if not regle:
                domaine = self.env["product.config.domain"].create(
                    {"name": "%s / %s" % (ligne.attribute_id.name, valeur.name)}
                )
                regle = self.env["product.config.line"].create({
                    "product_tmpl_id": self.id,
                    "attribute_line_id": ligne.id,
                    "value_ids": [(6, 0, [valeur.id])],
                    "domain_id": domaine.id,
                })
            cible = regle.domain_id
        else:
            if not ligne.visibility_domain_id:
                ligne.visibility_domain_id = self.env["product.config.domain"].create(
                    {"name": ligne.attribute_id.name}
                )
            cible = ligne.visibility_domain_id
        # ⚠️ **LE DIALOGUE EST CELUI DE LA BARRE DE RECHERCHE**, demandé par
        # Gerry : *« je voulais retrouver la même fenêtre que pour les filtres de
        # la barre de recherche »*. La liste éditable d'OCA — attribut, condition,
        # valeurs, opérateur en colonnes — disait la même chose, mais dans un
        # vocabulaire que personne d'autre dans Odoo n'emploie.
        #
        # ⓘ Le stockage ne bouge pas : l'assistant traduit dans les deux sens
        # (`to_odoo_domain` / `from_odoo_domain`), et une condition reste faite
        # d'ENREGISTREMENTS (D-080).
        return self.env["product.configurator.condition"].open_for(self, cible)

    def configurator_open_step(self, line_id):
        """Ouvre les réglages d'une étape — sa condition, et sa vue 3D.

        ⚠️ Même raison : « Configuration Steps » était le seul endroit d'où l'on
        règle la **condition de visibilité** d'une étape (D-086) et sa caméra.
        L'ordre et l'appartenance, eux, sont déduits depuis D-202 — c'est tout ce
        que cette section avait cessé de servir, pas le reste.
        """
        self.ensure_one()
        ligne = self.env["product.template.attribute.line"].browse(line_id)
        etape = self.config_step_line_ids.filtered(
            lambda sl: sl.config_step_id == ligne.config_step_id
        )[:1]
        if not etape:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": etape.display_name,
            "res_model": "product.config.step.line",
            "res_id": etape.id,
            "view_mode": "form",
            "views": [
                (self.env.ref(
                    "product_configurator_fa.product_config_step_line_form").id,
                 "form"),
            ],
            "target": "new",
            "context": {"product_tmpl_id": self.id},
        }

    # ─ POSER UNE ÉTAPE COMME ON POSE UNE SECTION — 2026-08-29 ───────────────
    #
    # ⚠️ **LE DIALOGUE A DISPARU, PAS LA CONTRAINTE.** Gerry : *« quand on ajoute
    # une étape, le comportement doit être identique à ajouter une section : une
    # ligne se crée, on la nomme, puis on la déplace à sa position »*. C'est le
    # geste des lignes de commande, et il vaut mieux que l'assistant : on ne
    # choisit plus À L'AVANCE une chose qu'on saura mieux en la voyant.
    #
    # ⚠️ Mais une étape reste un MARQUEUR porté par la ligne qui l'ouvre (D-202) :
    # elle ne peut pas se poser « en bas » comme une section, puisqu'il n'y a
    # aucune ligne sous la dernière. On la pose donc sur la DERNIÈRE LIGNE LIBRE
    # — au plus bas qu'un marqueur puisse aller —, et le glisser fait le reste.

    def configurator_add_step(self):
        """Crée une étape NEUVE et la pose au plus bas — elle attend son nom.

        ⓘ Une étape neuve à chaque clic, jamais une étape existante réemployée :
        c'est ce qui rend le renommage sans conséquence pour les autres produits.
        Réemployer une étape du catalogue reste possible en la désignant depuis
        ses propres écrans.

        :return: l'identifiant de l'étape créée — l'arbre s'en sert pour ouvrir
            sa saisie de nom, comme une section fraîche.
        """
        self.ensure_one()
        if not self.attribute_line_ids:
            raise UserError(
                self.env._(
                    "Add an attribute first: a step opens ON an attribute — it "
                    "and everything below belong to it."
                )
            )
        # ⚠️ La DERNIÈRE ligne libre, en remontant. Poser le marqueur sur une
        # ligne qui en porte déjà un remplacerait une étape par une autre —
        # silencieusement, et sans que rien ne l'ait demandé.
        libre = self.attribute_line_ids.sorted().filtered(
            lambda ligne: not ligne.config_step_id
        )[-1:]
        if not libre:
            raise UserError(
                self.env._(
                    "Every attribute already opens a step. Move one out of the "
                    "way before adding another."
                )
            )
        etape = self.env["product.config.step"].create(
            {"name": self.env._("New Step")}
        )
        libre.config_step_id = etape
        return etape.id

    def configurator_rename_step(self, step_id, name):
        """Renomme une étape depuis son bandeau.

        ⚠️ **LE NOM EST CELUI DE L'ENREGISTREMENT, DONC PARTAGÉ.**
        `product.config.step` est une fiche de catalogue : renommer une étape que
        d'autres produits emploient les renomme aussi. En pratique le cas est
        rare — `configurator_add_step` crée une étape NEUVE à chaque fois, donc
        celle qu'on renomme vient d'être créée pour ce produit-ci.

        ⓘ La garde ci-dessous n'est pas décorative : sans elle, l'arbre d'un
        produit pourrait renommer n'importe quelle étape du catalogue.
        """
        self.ensure_one()
        etape = self.env["product.config.step"].browse(step_id)
        if etape not in self.config_step_line_ids.config_step_id:
            raise UserError(
                self.env._("This step is not declared on this product.")
            )
        nom = (name or "").strip()
        if not nom:
            # ⓘ `name` est obligatoire : un nom vidé ne s'écrit pas, il s'ignore.
            # Le bandeau garde le sien, et rien ne se perd.
            return False
        etape.name = nom
        return True

    def configurator_move_step(self, step_id, line_id):
        """Déplace le bandeau : l'étape s'ouvre désormais SUR cette ligne.

        ⚠️ **DÉPLACER UN BANDEAU N'EST PAS DÉPLACER UNE LIGNE.** L'étape n'a pas
        de rang à elle (D-202) : son rang est celui de la ligne qui l'ouvre. On
        efface donc le marqueur là où il était, et on le pose ici — après quoi
        tout ce qui suit lui appartient, jusqu'à l'étape suivante.
        """
        self.ensure_one()
        etape = self.env["product.config.step"].browse(step_id)
        cible = self.env["product.template.attribute.line"].browse(line_id)
        if cible not in self.attribute_line_ids:
            raise UserError(
                self.env._("This attribute line does not belong to this product.")
            )
        # ⚠️ Une ligne n'ouvre qu'UNE étape. Déposer un bandeau sur une ligne qui
        # en porte déjà un écraserait l'autre étape sans le dire.
        if cible.config_step_id and cible.config_step_id != etape:
            raise UserError(
                self.env._(
                    "“%(other)s” already opens on this attribute. Move it first.",
                    other=cible.config_step_id.name,
                )
            )
        ancienne = self.attribute_line_ids.filtered(
            lambda ligne: ligne.config_step_id == etape
        )
        (ancienne - cible).config_step_id = False
        cible.config_step_id = etape
        return True

    def configurator_reorder(self, line_ids):
        """Réordonne les lignes d'attribut — l'ordre PORTE l'appartenance.

        ⚠️ Déplacer une ligne peut changer son étape (D-202), en silence. C'est
        assumé ; c'est pourquoi l'arbre redessine ses bandeaux après chaque
        déplacement, au lieu d'attendre un rechargement.
        """
        self.ensure_one()
        lignes = self.env["product.template.attribute.line"].browse(line_ids)
        for rang, ligne in enumerate(lignes, start=1):
            ligne.sequence = rang * 10
        return True

    def configurator_reorder_values(self, line_id, value_ids):
        """Réordonne les VALEURS d'un attribut — l'ordre est celui de l'attribut.

        ⚠️ **CET ORDRE EST GLOBAL, ET C'EST ASSUMÉ.** Une valeur est un
        `product.attribute.value` : son rang vit dans sa `sequence`, qui
        appartient à l'ATTRIBUT et non au produit (`_order` du cœur :
        *attribute_id, sequence, id*). Déplacer « brut » depuis un produit le
        déplace donc partout où l'attribut sert — dans les autres produits comme
        dans Configuration → Attributs. Arbitré par Gerry le 2026-08-29 : c'est
        le seul ordre qui existe, et en inventer un par produit obligerait tout
        ce qui affiche des valeurs à le relire.

        ⚠️ **ON NE RENUMÉROTE PAS QUE LES VALEURS DU PRODUIT.** Un produit ne
        porte souvent qu'une PART des valeurs de l'attribut ; leur donner
        10, 20, 30 les jetterait devant celles qu'il n'emploie pas, qui gardent
        leur propre séquence. On renumérote donc l'attribut ENTIER, en ne
        permutant les valeurs demandées qu'entre les RANGS qu'elles occupaient
        déjà : les autres ne bougent pas d'un cran.
        """
        self.ensure_one()
        ligne = self.env["product.template.attribute.line"].browse(line_id)
        demandees = self.env["product.attribute.value"].browse(value_ids)
        # ⚠️ Garde-fou : on n'ordonne QUE ce que cette ligne porte. Un
        # identifiant venu d'ailleurs réordonnerait un attribut que l'écran ne
        # montrait même pas.
        if demandees != ligne.value_ids:
            raise UserError(
                self.env._(
                    "The values to reorder must be exactly the ones this "
                    "attribute carries on this product."
                )
            )
        toutes = list(ligne.attribute_id.value_ids)
        rangs = [i for i, valeur in enumerate(toutes) if valeur in demandees]
        for rang, valeur in zip(rangs, demandees):
            toutes[rang] = valeur
        for rang, valeur in enumerate(toutes, start=1):
            valeur.sequence = rang * 10
        return True

    config_line_ids = fields.One2many(
        comodel_name="product.config.line",
        inverse_name="product_tmpl_id",
        string="Attribute Dependencies",
        copy=False,
    )

    config_image_ids = fields.One2many(
        comodel_name="product.config.image",
        inverse_name="product_tmpl_id",
        string="Configuration Images",
        copy=True,
    )

    attribute_value_line_ids = fields.One2many(
        comodel_name="product.attribute.value.line",
        inverse_name="product_tmpl_id",
        string="Attribute Value Lines",
        copy=True,
    )

    attribute_line_val_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        compute="_compute_template_attr_vals",
        store=False,
    )

    config_step_line_ids = fields.One2many(
        comodel_name="product.config.step.line",
        inverse_name="product_tmpl_id",
        string="Configuration Lines",
        copy=False,
    )

    mako_tmpl_name = fields.Text(
        string="Variant name",
        help="Generate Name based on Mako Template",
        copy=True,
    )

    # We are calculating weight of variants based on weight of
    # product-template so that no need of compute and inverse on this
    weight = fields.Float(
        compute="_compute_weight",
        inverse="_set_weight",  # pylint: disable=C8110
        search="_search_weight",
        store=False,
    )
    weight_dummy = fields.Float(
        string="Manual Weight",
        digits="Stock Weight",
        help="Manual setting of product template weight",
    )

    def _compute_weight(self):
        config_products = self.filtered(lambda template: template.config_ok)
        for product in config_products:
            product.weight = product.weight_dummy
        standard_products = self - config_products
        return super(ProductTemplate, standard_products)._compute_weight()

    def _set_weight(self):
        for product_tmpl in self:
            product_tmpl.weight_dummy = product_tmpl.weight
            if not product_tmpl.config_ok:
                super(ProductTemplate, product_tmpl)._set_weight()
        return

    def _search_weight(self, operator, value):
        return [("weight_dummy", operator, value)]

    def _check_default_values(self):
        default_val_ids = (
            self.attribute_line_ids.filtered(lambda line: line.default_val)
            .mapped("default_val")
            .ids
        )

        cfg_session_obj = self.env["product.config.session"]
        try:
            cfg_session_obj.validate_configuration(
                value_ids=default_val_ids, product_tmpl_id=self.id, final=False
            )
        except ValidationError as exc:
            raise ValidationError(exc.args[0]) from exc
        except Exception as exc:
            raise ValidationError(
                self.env._("Default values provided generate an invalid configuration")
            ) from exc

    @api.constrains("config_line_ids", "attribute_line_ids")
    def _check_default_value_domains(self):
        for template in self:
            try:
                template._check_default_values()
            except ValidationError as exc:
                raise ValidationError(
                    self.env._(
                        "Restrictions added make the current default values "
                        "generate an invalid configuration.\
                      \n%s"
                    )
                    % (exc.args[0])
                ) from exc

    # ─ QB : ON PRÉVIENT, ON NE CONVERTIT NI NE REFUSE — D-200 ───────────────
    #
    # Arbitrage de Gerry : *« lorsqu'un produit devient configurable on prévient si
    # des exclusions sont dans le produit »*. Ni conversion automatique, ni refus de
    # la bascule — un avertissement.
    #
    # ⚠️ **CES EXCLUSIONS SONT DÉJÀ SANS EFFET, et c'est tout le sujet.** Le
    # configurateur ne les lit pas : aucune occurrence de `exclude_for`,
    # `_is_combination_possible` ni `_get_attribute_exclusions` dans ce module. Et
    # `_create_variant_ids` saute les produits configurables, ce qui prive les
    # exclusions de leur seul autre consommateur. L'avertissement ne change donc
    # aucun comportement : **il rend explicite un silence**. Aujourd'hui l'interface
    # laisse croire qu'un réglage agit, ce qui est pire que de ne pas l'offrir.
    #
    # ⓘ Pourquoi un `onchange` et pas une contrainte : une contrainte ne sait que
    # refuser, et Gerry a écarté le refus. Un avertissement se rend par
    # `{"warning": ...}`, que seul un `onchange` peut retourner.
    #
    # ⚠️ Corollaire à connaître : `toggle_config()` — l'ancienne action, encore
    # appelable — ne déclenche AUCUN onchange. La bascule par la case à cocher
    # avertit, la bascule par le bouton non. C'est le prix de l'avertissement, et
    # c'est aussi une raison de plus de ne garder que la case (D-186).
    @api.onchange("config_ok")
    def _onchange_config_ok_warns_about_exclusions(self):
        if not self.config_ok or not self._origin:
            return None
        tmpl_id = self._origin.id
        exclusions = self.env["product.template.attribute.exclusion"].search_count(
            [
                "|",
                ("product_tmpl_id", "=", tmpl_id),
                ("product_template_attribute_value_id.product_tmpl_id", "=", tmpl_id),
            ]
        )
        if not exclusions:
            return None
        return {
            "warning": {
                "title": self.env._("Exclusions will no longer apply"),
                "message": self.env._(
                    "This product carries %s native exclusion(s). A configurable "
                    "product does not read them: state these restrictions as "
                    "configurator conditions instead. The exclusions are left "
                    "untouched — nothing is deleted or converted.",
                    exclusions,
                ),
            }
        }

    def toggle_config(self):
        for record in self:
            record.config_ok = not record.config_ok

    def _create_variant_ids(self):
        """Prevent configurable products from creating variants as these serve
        only as a template for the product configurator"""
        templates = self.filtered(lambda t: not t.config_ok)
        if not templates:
            return None
        return super(ProductTemplate, templates)._create_variant_ids()

    def unlink(self):
        """- Prevent the removal of configurable product templates
            from variants
        - Patch for check access rights of user(configurable products)"""
        configurable_templates = self.filtered(lambda template: template.config_ok)
        if configurable_templates:
            configurable_templates[:1].check_config_user_access()
        for config_template in configurable_templates:
            variant_unlink = config_template.env.context.get(
                "unlink_from_variant", False
            )
            if variant_unlink:
                self -= config_template
        res = super().unlink()
        return res

    def copy(self, default=None):
        """Copy restrictions, config Steps and attribute lines
        ith product template"""
        if not default:
            default = {}
        self = self.with_context(check_constraint=False)
        res = super().copy(default=default)

        # Attribute lines
        attribute_line_dict = {}
        for line in res.attribute_line_ids:
            attribute_line_dict.update({line.attribute_id.id: line.id})

        # Restrictions
        for line in self.config_line_ids:
            old_restriction = line.domain_id
            new_restriction = old_restriction.copy()
            config_line_default = {
                "product_tmpl_id": res.id,
                "domain_id": new_restriction.id,
            }
            new_attribute_line_id = attribute_line_dict.get(
                line.attribute_line_id.attribute_id.id, False
            )
            if not new_attribute_line_id:
                continue
            config_line_default.update({"attribute_line_id": new_attribute_line_id})
            line.copy(config_line_default)

        # ─ Config steps ────────────────────────────────────────────────────
        #
        # ⚠️ L'APPARTENANCE N'EST PLUS À RECOPIER (D-202) : elle est déduite de
        # l'ordre, et les lignes d'attribut de la copie portent déjà leurs
        # marqueurs — donc les étapes de la copie sont déjà DÉCLARÉES quand on
        # arrive ici. Recopier la ligne d'étape violerait l'unicité
        # `(produit, étape)`. Ce qui reste à reporter, c'est ce que la ligne
        # d'étape porte EN PROPRE : sa condition de visibilité.
        step_line_obj = self.env["product.config.step.line"]
        for line in self.config_step_line_ids:
            jumelle = step_line_obj.search([
                ("product_tmpl_id", "=", res.id),
                ("config_step_id", "=", line.config_step_id.id),
            ], limit=1)
            if jumelle:
                jumelle.visibility_domain_id = line.visibility_domain_id
            else:
                # Une étape que plus aucune ligne n'ouvre sur la copie : on la
                # garde tout de même, pour ne pas perdre ses réglages.
                line.copy({"product_tmpl_id": res.id})
        return res

    def configure_product(self):
        """launches a product configurator wizard with a linked
        template in order to configure new product."""
        return self.with_context(product_tmpl_id_readonly=True).create_config_wizard(
            click_next=False
        )

    def create_config_wizard(
        self,
        model_name="product.configurator",
        extra_vals=None,
        click_next=True,
    ):
        """create product configuration wizard
        - return action to launch wizard
        - click on next step based on value of click_next"""
        wizard_obj = self.env[model_name]
        wizard_vals = {"product_tmpl_id": self.id}
        if extra_vals:
            wizard_vals.update(extra_vals)
        wizard = wizard_obj.create(wizard_vals)
        if click_next:
            action = wizard.action_next_step()
        else:
            wizard_obj = wizard_obj.with_context(
                wizard_model=model_name,
                allow_preset_selection=True,
            )
            action = wizard_obj.get_wizard_action(wizard=wizard)
        return action

    @api.model
    def _check_config_group_rights(self):
        """Return True/False from system parameter
        - Signals access rights needs to check or not
        :Params: return : boolean"""
        ICPSudo = self.env["ir.config_parameter"].sudo()
        manager_product_configuration_settings = ICPSudo.get_param(
            "product_configurator_fa.manager_product_configuration_settings"
        )
        return manager_product_configuration_settings

    @api.model
    def check_config_user_access(self):
        """Check user have access to perform action(create/write/delete)
        on configurable products"""
        if not self._check_config_group_rights():
            return True
        config_manager = self.env.user.has_group(
            "product_configurator_fa.group_product_configurator_fa_manager"
        )
        user_root = self.env.ref("base.user_root")
        user_admin = self.env.ref("base.user_admin")
        if (
            config_manager
            or self.env.user.id in [user_root.id, user_admin.id]
            or self.env.su
        ):
            return True
        raise ValidationError(
            self.env._(
                "Sorry, you are not allowed to create/change this kind of "
                "document. For more information please contact your manager."
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        """Patch for check access rights of user(configurable products)"""
        for vals in vals_list:
            config_ok = vals.get("config_ok", False)
            if config_ok:
                self.check_config_user_access()
        return super().create(vals_list)

    def write(self, vals):
        """Patch for check access rights of user(configurable products)"""
        change_config_ok = "config_ok" in vals
        configurable_templates = self.filtered(lambda template: template.config_ok)
        if change_config_ok or configurable_templates:
            self[:1].check_config_user_access()

        return super().write(vals)

    @api.constrains("config_line_ids")
    def _check_config_line_domain(self):
        attribute_line_ids = self.attribute_line_ids
        tmpl_value_ids = attribute_line_ids._configurator_value_ids()
        tmpl_attribute_ids = attribute_line_ids.mapped("attribute_id")
        error_message = False
        for domain_id in self.config_line_ids.mapped("domain_id"):
            domain_attr_ids = domain_id.domain_line_ids.mapped("attribute_id")
            domain_value_ids = domain_id.domain_line_ids.mapped("value_ids")
            invalid_value_ids = domain_value_ids - tmpl_value_ids
            invalid_attribute_ids = domain_attr_ids - tmpl_attribute_ids
            if not invalid_attribute_ids and not invalid_value_ids:
                continue
            if not error_message:
                error_message = self.env._(
                    "Following Attribute/Value from restriction "
                    "are not present in template attributes/values. "
                    "Please make sure you are adding right restriction"
                )
            error_message += self.env._("\nRestriction: %s", domain_id.name)
            error_message += (
                invalid_attribute_ids
                and self.env._(
                    "\nAttribute/s: %s", ", ".join(invalid_attribute_ids.mapped("name"))
                )
                or ""
            )
            error_message += (
                invalid_value_ids
                and self.env._(
                    "\nValue/s: %s\n", ", ".join(invalid_value_ids.mapped("name"))
                )
                or ""
            )
        if error_message:
            raise ValidationError(error_message)


    def _price_compute(
        self, price_type, uom=None, currency=None, company=None, date=False
    ):
        """Le prix d'une configuration EN COURS, avant qu'aucune variante n'existe.

        ⚠️ Rien n'est créé avant le devis (D-082) : il n'y a donc pas de
        `product.product` à qui demander un prix pendant la configuration. Le
        prix de grille entre par le CONTEXTE, et tout le reste — pourcentages,
        formules, devise, arrondis, cascades de listes de prix — continue de
        marcher sans qu'on y touche, parce qu'on emprunte le chemin d'Odoo au
        lieu d'en refaire un (D-092).

        Le contexte porte un DICTIONNAIRE par template, et non un montant :
        `_price_compute` peut recevoir plusieurs enregistrements, et une valeur
        unique se serait appliquée à tous.

        source : addons/product/models/product_template.py:688 — voir P17 du
        registre des points de contact.
        """
        prices = super()._price_compute(
            price_type, uom=uom, currency=currency, company=company, date=date
        )
        base_prices = self.env.context.get("configurator_base_prices") or {}
        if price_type != "list_price" or not base_prices:
            return prices
        company = company or self.env.company
        date = date or fields.Date.context_today(self)
        for template in self.with_company(company):
            if template.id not in base_prices:
                continue
            price = base_prices[template.id] + template._get_attributes_extra_price()
            if uom:
                price = template.uom_id._compute_price(price, uom)
            if currency:
                price = template.currency_id._convert(price, currency, company, date)
            prices[template.id] = price
        return prices

        domain_obj = self.env["product.config.domain"]
        template = self.browse(template_id)
        for line in template.attribute_line_ids:
            attribute = line.attribute_id
            fields[domain_obj._attribute_field_name(attribute)] = {
                "string": attribute.name,
                "type": "many2one",
                "relation": "product.attribute.value",
                "domain": [("attribute_id", "=", attribute.id)],
                "searchable": True,
                "sortable": False,
                "store": False,
                "readonly": True,
            }
            # ⓘ C4, D-201 — un attribut de type PRODUIT se teste aussi par ses
            # produits. Le champ est offert EN PLUS, jamais à la place : les
            # deux formes coexistent, et une règle déjà écrite sur des valeurs
            # doit continuer de s'éditer telle quelle.
            if attribute.value_type == "product":
                fields[domain_obj._product_field_name(attribute)] = {
                    "string": self.env._(
                        "%(attribute)s (products)", attribute=attribute.name
                    ),
                    "type": "many2one",
                    "relation": "product.product",
                    "searchable": True,
                    "sortable": False,
                    "store": False,
                    "readonly": True,
                }
        return fields

    price_grid_ids = fields.One2many(
        comodel_name="product.price.grid",
        inverse_name="product_tmpl_id",
        string="Price Grids",
    )

    # ─ LA GRILLE SE RANGE AVEC LA LISTE DE PRIX — D-214 ─────────────────────
    #
    # Question de Gerry : *« la grille de prix et la liste de prix ne devraient
    # pas être au même endroit ? »*
    #
    # ⓘ Elles ne décident PAS la même chose — la grille **produit** le prix d'un
    # produit dimensionné (D-083, D-093), la liste de prix **l'ajuste** pour un
    # client ou une quantité. Mais elles répondent à la même question de
    # l'utilisateur : *« où se règle le prix ? »*. Deux portes éloignées pour une
    # seule question, c'est une porte de trop.
    #
    # ⇒ La grille prend un bouton d'en-tête **à côté** de celui d'Odoo, et quitte
    # l'onglet du configurateur — qui ne garde que l'arbre, comme la maquette.
    price_grid_count = fields.Integer(compute="_compute_price_grid_count")

    @api.depends("price_grid_ids", "price_grid_ids.active")
    def _compute_price_grid_count(self):
        for template in self:
            template.price_grid_count = len(template.price_grid_ids)

    def action_open_price_grids(self):
        """Les grilles de CE produit.

        ⚠️ `views` explicite : cette action part vers un bouton de vue, donc elle
        serait complétée — mais la laisser incomplète ferait dépendre son bon
        fonctionnement du chemin emprunté ([[L-165]]). On l'écrit autosuffisante.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Price grids"),
            "res_model": "product.price.grid",
            "view_mode": "list,form",
            "views": [
                (self.env.ref(
                    "product_configurator_fa.product_price_grid_list_view").id, "list"),
                (self.env.ref(
                    "product_configurator_fa.product_price_grid_form_view").id, "form"),
            ],
            "domain": [("product_tmpl_id", "=", self.id)],
            "context": {"default_product_tmpl_id": self.id},
        }

    # ⚠️ **LE BANDEAU « PAS DE GRILLE » A ÉTÉ RETIRÉ — il était FAUX.** Constat
    # de Gerry (2026-08-28) : *« on peut configurer un produit sans grille de
    # prix »*. Et le code le dit : `_get_config_grid_price` rend `None` sans
    # grille, et l'appelant retombe sur le `list_price` du modèle. Le message
    # annonçait donc un blocage qui n'existe pas — pire qu'un silence, puisqu'il
    # décourage un usage licite.
    #
    # ⓘ Le champ calculé qui le portait part avec lui : un calcul que plus rien
    # ne lit est une dépense et une promesse — celle qu'il dit encore quelque
    # chose de vrai.

    def _get_price_grid(self, date=None):
        """La grille en vigueur à cette date — au plus une (D-083)."""
        self.ensure_one()
        # ⚠️ Odoo passe la date tantôt en `date`, tantôt en chaîne (un contexte,
        # une valeur de devis) : comparer sans convertir lève un TypeError que
        # rien n'annonce à la lecture.
        date = fields.Date.to_date(date) or fields.Date.context_today(self)
        # ⚠️ `sudo` — SANS LUI, LA BOUTIQUE RÉPOND 403 À TOUT VISITEUR ANONYME.
        # `_price_compute` passe ici pour n'importe quel lecteur d'un prix, et
        # l'utilisateur PUBLIC n'a aucune ACL sur `product.price.grid` : les
        # droits posés en D-093 s'arrêtent au portail, parce qu'il n'y avait pas
        # de site quand ils ont été écrits. Le rendu de `website_sale.product`
        # levait donc un `AccessError` sur le premier produit venu — configurable
        # ou non.
        # ⓘ `sudo` plutôt qu'une ACL publique : ce que le visiteur doit obtenir
        # est le PRIX, pas la grille. Une ligne d'ACL rendrait les paliers et
        # les cellules lisibles partout ; ici la lecture reste enfermée dans le
        # calcul, et le `sudo` porte aussi les paliers et cellules que
        # `get_price` traverse ensuite.
        grids = self.sudo().price_grid_ids.filtered(
            lambda grid: (not grid.date_start or grid.date_start <= date)
            and (not grid.date_end or grid.date_end >= date)
        )
        return grids[:1]

    def _grid_axis_lines(self):
        """Les deux lignes d'attribut qui portent les rôles d'axe — D-098."""
        self.ensure_one()
        lines = {}
        for line in self.attribute_line_ids:
            if line.dimension_role:
                lines[line.dimension_role] = line
        return lines

    def _grid_surface(self, x_value, y_value):
        """La surface en m² — le PRODUIT DES DEUX AXES, rien d'autre (D-161).

        ⚠️ Première conversion d'unités du module : D-160 pose qu'un attribut
        porte une unité et que personne ne convertit, mais 2 400 mm × 2 100 mm
        ne fait pas 5 040 000 m². Un axe SANS unité est refusé plutôt que
        supposé en millimètres — supposer ici, c'est se tromper d'un facteur
        un million sans que rien ne le dise.
        """
        self.ensure_one()
        axis_lines = self._grid_axis_lines()
        metres = []
        for role, value in (("axis_x", x_value), ("axis_y", y_value)):
            line = axis_lines.get(role)
            uom = line.attribute_id.uom_id if line else False
            if not uom:
                raise ValidationError(
                    self.env._(
                        "A surface cannot be computed on %(product)s: the grid "
                        "axis has no unit of measure.",
                        product=self.display_name,
                    )
                )
            reference = uom.category_id.uom_ids.filtered(
                lambda unit: unit.uom_type == "reference"
            )
            if not reference:
                raise ValidationError(
                    self.env._("The unit %(uom)s has no reference unit", uom=uom.name)
                )
            metres.append(uom._compute_quantity(value, reference, round=False))
        return metres[0] * metres[1]

    def _refresh_grid_list_price(self):
        """Le `list_price` du template devient le « À PARTIR DE » — D-093.

        Sans cela, la fiche annoncerait « Prix de vente : 200 € » alors
        qu'aucune vente ne se ferait à ce prix.
        """
        for template in self:
            grid = template._get_price_grid()
            if grid:
                template.list_price = grid._lowest_price()


class ProductProduct(models.Model):
    _inherit = "product.product"
    _rec_name = "config_name"

    grid_price = fields.Float(
        string="Grid Price",
        digits="Product Price",
        readonly=True,
        help="Price read in the grid in force TODAY. Informative only — a "
        "quotation always reads the grid at its own date.",
    )

    def _get_grid_dimensions(self):
        """Les deux cotes de cette variante, lues dans ses valeurs d'attribut.

        Elles y sont parce que le lot 2 les y a rangées (D-081) : une dimension
        n'est pas une valeur personnalisée, c'est une valeur d'attribut — et
        c'est ce qui la rend lisible ici, sans session ni saisie.
        """
        self.ensure_one()
        dimensions = {}
        for ptav in self.product_template_attribute_value_ids:
            role = ptav.attribute_line_id.dimension_role
            if not role:
                continue
            try:
                dimensions[role] = float(ptav.product_attribute_value_id.name)
            except (TypeError, ValueError):
                # Une valeur d'axe qui n'est pas un nombre ne dit rien : mieux
                # vaut pas de prix de grille qu'un prix lu de travers.
                return {}
        return dimensions

    def _get_grid_price(self, date=None):
        """Le prix de grille de cette variante, ou `None` — jamais zéro."""
        self.ensure_one()
        grid = self.product_tmpl_id._get_price_grid(date=date)
        if not grid:
            return None
        dimensions = self._get_grid_dimensions()
        if "axis_x" not in dimensions or "axis_y" not in dimensions:
            return None
        return grid.get_price(dimensions["axis_x"], dimensions["axis_y"])

    def _get_attributes_extra_price_sqm(self):
        """La part des suppléments exprimée AU MÈTRE CARRÉ — D-162.

        ⚠️ Elle ne peut pas passer par `price_extra`, que tout Odoo somme
        comme un montant : 25 €/m² y serait ajouté comme 25 €, sans erreur et
        sans trace.
        """
        self.ensure_one()
        rated = self.product_template_attribute_value_ids.filtered(
            lambda ptav: ptav.attribute_line_id.price_mode == "per_sqm"
            and ptav.price_extra_sqm
        )
        if not rated:
            return 0.0
        dimensions = self._get_grid_dimensions()
        if "axis_x" not in dimensions or "axis_y" not in dimensions:
            return 0.0
        surface = self.product_tmpl_id._grid_surface(
            dimensions["axis_x"], dimensions["axis_y"]
        )
        return sum(rated.mapped("price_extra_sqm")) * surface

    def _price_compute(
        self, price_type, uom=None, currency=None, company=None, date=False
    ):
        """Pour un produit à grille, `list_price` REND LE PRIX DE GRILLE — D-093.

        ⚠️ C'est le point unique par lequel tout Odoo demande le prix d'un
        produit : listes de prix, devis, rapports, portail. Une remise
        « professionnel −10 % » part de `list_price` (le défaut d'une règle) :
        sans cette surcharge, elle s'appliquerait aux 200 € du template au lieu
        des 540 € de la grille, et le devis afficherait un montant plausible.

        La « quatrième base » — ajouter `grid_price` aux choix de `base` d'une
        règle — a été écartée : il faudrait PENSER à la choisir, et l'oubli est
        silencieux.

        source : addons/product/models/product_product.py:794 — les étapes
        (extras, unité, devise) sont reprises telles quelles ; voir P1 et P2 du
        registre des points de contact.
        """
        if price_type != "list_price":
            return super()._price_compute(
                price_type, uom=uom, currency=currency, company=company, date=date
            )
        company = company or self.env.company
        date = date or fields.Date.context_today(self)
        prices = super()._price_compute(
            price_type, uom=uom, currency=currency, company=company, date=date
        )
        for product in self.with_company(company):
            grid_price = product._get_grid_price(date=date)
            if grid_price is None:
                continue
            price = (
                grid_price
                + product._get_attributes_extra_price()
                + product._get_attributes_extra_price_sqm()
            )
            if uom:
                price = product.uom_id._compute_price(price, uom)
            if currency:
                price = product.currency_id._convert(price, currency, company, date)
            prices[product.id] = price
        return prices

    @api.model
    def _cron_refresh_grid_price(self):
        """Rafraîchit le prix de grille STOCKÉ — informatif, jamais autorité.

        ⚠️ D-084 : une grille datée rend tout champ stocké faux le jour où un
        nouveau tarif prend effet. Ce champ dit « le prix en vigueur ce jour » ;
        entre minuit et ce passage, il est périmé. Acceptable pour un
        affichage, jamais pour un devis — qui lit la grille à SA date.
        """
        products = self.search([("config_ok", "=", True)])
        for product in products:
            grid_price = product._get_grid_price()
            if grid_price is not None and grid_price != product.grid_price:
                product.grid_price = grid_price

    @api.constrains("product_template_attribute_value_ids")
    def _check_duplicate_product(self):
        """Check for prducts with same attribute values/custom values"""
        for product in self:
            if not product.config_ok:
                continue

            # At the moment, I don't have enough confidence with my
            # understanding of binary attributes, so will leave these
            # as not matching...
            # In theory, they should just work, if they are set to "non search"
            # in custom field def!
            # TODO: Check the logic with binary attributes
            config_session_obj = product.env["product.config.session"]
            ptav_ids = product.product_template_attribute_value_ids.mapped(
                "product_attribute_value_id"
            )
            duplicates = config_session_obj.search_variant(
                product_tmpl_id=product.product_tmpl_id,
                value_ids=ptav_ids.ids,
            ).filtered(lambda p, product=product: p.id != product.id)

            if duplicates:
                raise ValidationError(
                    self.env._(
                        "Configurable Products cannot have duplicates "
                        "(identical attribute values)"
                    )
                )

    def _get_config_name(self):
        """Name for configured products
        :param: return : String"""
        self.ensure_one()
        return self.name

    def _get_mako_context(self, buf):
        """Return context needed for computing product name based
        on mako-tamplate define on it's product template"""
        self.ensure_one()
        ptav_ids = self.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id"
        )
        return Context(
            buf,
            product=self,
            attribute_values=ptav_ids,
            steps=self.product_tmpl_id.config_step_line_ids,
            template=self.product_tmpl_id,
        )

    def _get_mako_tmpl_name(self):
        """Compute and return product name based on mako-tamplate
        define on it's product template"""
        self.ensure_one()
        if self.mako_tmpl_name:
            try:
                mytemplate = Template(self.mako_tmpl_name or "")
                buf = StringIO()
                ctx = self._get_mako_context(buf)
                mytemplate.render_context(ctx)
                return buf.getvalue()
            except Exception:
                _logger.error(
                    self.env._("Error while calculating mako product name: %s")
                    % self.display_name
                )
        return self.display_name

    @api.depends("product_template_attribute_value_ids.weight_extra")
    def _compute_product_weight_extra(self):
        for product in self:
            product.weight_extra = sum(
                product.mapped("product_template_attribute_value_ids.weight_extra")
            )

    def _compute_product_weight(self):
        for product in self:
            if product.config_ok:
                tmpl_weight = product.product_tmpl_id.weight
                product.weight = tmpl_weight + product.weight_extra
            else:
                product.weight = product.weight_dummy

    def _search_product_weight(self, operator, value):
        return [("weight_dummy", operator, value)]

    def _inverse_product_weight(self):
        """Store weight in dummy field"""
        self.weight_dummy = self.weight

    config_name = fields.Char(
        string="Configuration Name", compute="_compute_config_name"
    )
    weight_extra = fields.Float(compute="_compute_product_weight_extra")
    weight_dummy = fields.Float(string="Manual Weight", digits="Stock Weight")
    weight = fields.Float(
        compute="_compute_product_weight",
        inverse="_inverse_product_weight",
        search="_search_product_weight",
        store=False,
    )

    # product preset
    config_preset_ok = fields.Boolean(string="Is Preset")

    def _compute_config_name(self):
        """Compute the name of the configurable products and use template
        name for others"""
        for product in self:
            if product.config_ok:
                product.config_name = product._get_config_name()
            else:
                product.config_name = product.name

    def reconfigure_product(self):
        """launches a product configurator wizard with a linked
        template and variant in order to re-configure an existing product.
        It is essentially a shortcut to pre-fill configuration
        data of a variant"""
        self.ensure_one()

        extra_vals = {"product_id": self.id}
        return self.product_tmpl_id.create_config_wizard(extra_vals=extra_vals)

    @api.model
    def check_config_user_access(self, mode):
        """Check user have access to perform action(create/write/delete)
        on configurable products"""
        if not self.env["product.template"]._check_config_group_rights():
            return True
        config_manager = self.env.user.has_group(
            "product_configurator_fa.group_product_configurator_fa_manager"
        )
        config_user = self.env.user.has_group(
            "product_configurator_fa.group_product_configurator_fa"
        )
        user_root = self.env.ref("base.user_root")
        user_admin = self.env.ref("base.user_admin")
        if (
            config_manager
            or (config_user and mode not in ["delete"])
            or self.env.user.id in [user_root.id, user_admin.id]
        ):
            return True
        raise ValidationError(
            self.env._(
                "Sorry, you are not allowed to create/change this kind of "
                "document. For more information please contact your manager."
            )
        )

    def unlink(self):
        """- Signal unlink from product variant through context so
        removal can be stopped for configurable templates
        - check access rights of user(configurable products)"""
        config_product = any(p.config_ok for p in self)
        if config_product:
            self.env["product.product"].check_config_user_access(mode="delete")
        ctx = dict(self.env.context, unlink_from_variant=True)
        self.env.context = ctx
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        """Patch for check access rights of user(configurable products)"""
        for vals in vals_list:
            config_ok = vals.get("config_ok", False)
            if config_ok:
                self.check_config_user_access(mode="create")
        return super().create(vals_list)

    def write(self, vals):
        """Patch for check access rights of user(configurable products)"""
        change_config_ok = "config_ok" in vals
        configurable_products = self.filtered(lambda product: product.config_ok)
        if change_config_ok or configurable_products:
            self[:1].check_config_user_access(mode="write")

        return super().write(vals)

    def _compute_product_price_extra(self):
        standard_products = self.filtered(lambda product: not product.config_ok)
        config_products = self - standard_products
        if standard_products:
            result = super(
                ProductProduct, standard_products
            )._compute_product_price_extra()
        else:
            result = None
        for product in config_products:
            attribute_value_obj = self.env["product.attribute.value"]
            value_ids = (
                product.product_template_attribute_value_ids.product_attribute_value_id
            )
            extra_prices = attribute_value_obj.get_attribute_value_extra_prices(
                product_tmpl_id=product.product_tmpl_id.id, pt_attr_value_ids=value_ids
            )
            product.price_extra = sum(extra_prices.values())
        return result
