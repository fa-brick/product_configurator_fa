"""Ce qu'exécute `product.template.attribute.line` (BLL, D-541)."""
import logging
import re
from odoo import api, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ProductAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"

    @api.depends("sequence", "config_step_id", "product_tmpl_id",
                 "product_tmpl_id.attribute_line_ids.sequence",
                 "product_tmpl_id.attribute_line_ids.config_step_id")
    def _compute_config_step_owner_id(self):
        # ⓘ Groupé par produit : la réponse d'une ligne dépend de TOUTES celles du
        # même produit, et les relire une par une ferait une requête par ligne.
        par_produit = {}
        for line in self:
            par_produit.setdefault(line.product_tmpl_id, self.browse())
            par_produit[line.product_tmpl_id] |= line
        for template, lines in par_produit.items():
            # `_order` range déjà par `product_tmpl_id, sequence, id` — c'est
            # exactement l'ordre que l'utilisateur voit et déplace.
            ouverte = False
            for line in template.attribute_line_ids.sorted():
                if line.config_step_id:
                    ouverte = line.config_step_id
                if line in lines:
                    line.config_step_owner_id = ouverte
            # Une ligne sans produit (création en cours) n'appartient à rien.
            for line in lines.filtered(lambda l: not l.product_tmpl_id):
                line.config_step_owner_id = False

    @api.depends("sale_separately", "value_ids", "value_ids.product_id")
    def _compute_sale_separately_warning(self):
        """Les produits qui ne pourraient pas ALLER au panier — R4.6 de D-368.

        ⚠️ Une ligne à part se pose par la route du panier, qui refuse un produit non
        vendable ou non publié (`_is_add_to_cart_allowed`). Le dire ICI, au réglage, plutôt
        que de laisser la page découvrir le refus au moment de commander.
        ⓘ La publication n'existe qu'avec la boutique : lue seulement si le champ existe.
        """
        for line in self:
            if not line.sale_separately:
                line.sale_separately_warning = False
                continue
            blocked = []
            for value in line.value_ids.filtered("product_id"):
                tmpl = value.product_id.sudo().product_tmpl_id
                if not tmpl.sale_ok or ("is_published" in tmpl._fields and not tmpl.is_published):
                    blocked.append(value.product_id.sudo().display_name)
            line.sale_separately_warning = (
                self.env._("Cannot be ordered as it stands (not for sale, or not published "
                           "on the website): %s", ", ".join(blocked)) if blocked else False)

    # TODO: Order by dependencies first and then sequence so dependent fields
    # do not come before master field
    @api.onchange("attribute_id")
    def onchange_attribute(self):
        """Set default value of required/multi/cutom from attribute"""
        self.value_ids = False
        self.required = self.attribute_id.required
        self.multi = self.attribute_id.multi
        self.custom = self.attribute_id.val_custom
        self.price_mode = self.attribute_id.price_mode
        # Des bornes sur un attribut qui n'est plus numérique ne s'appliqueraient
        # jamais : les laisser en place, c'est afficher une règle inerte.
        if self.attribute_id.custom_type not in ("integer", "float"):
            self.has_min_val = False
            self.min_val = 0
            self.has_max_val = False
            self.max_val = 0
            self.step = 0
            self.bound_ids = False

        # TODO: Remove all dependencies pointed towards the attribute being
        # changed
    @api.onchange("value_ids")
    def onchange_values(self):
        if self.default_val and self.default_val not in self.value_ids:
            self.default_val = None

    # ─ ON PRÉVIENT AVANT DE DÉSACTIVER — B4, QC, D-205 ──────────────────────
    #
    # ⚠️ Le cœur archive en silence une valeur qu'il ne peut pas supprimer : sans
    # annonce, le même clic détruit ici et masque là, et l'écart ne se voit qu'après
    # coup, la valeur toujours là, grisée (D-205).
    #
    # ⓘ Un `onchange` et non une contrainte : le geste est légitime (D-205), on
    # annonce son effet réel.
    @api.onchange("value_ids")
    def _onchange_values_warns_about_deactivation(self):
        if not self._origin:
            return None
        # ⚠️ COMPARER DES IDENTIFIANTS, PAS DES ENSEMBLES. Dans un `onchange`, la
        # ligne est un enregistrement VIRTUEL : `self.value_ids` sort de son cache
        # tandis que `self._origin.value_ids` sort de la base, et la soustraction
        # de recordsets ne les annule pas toujours — mesuré, elle rendait « tout a
        # été retiré » alors qu'on venait d'AJOUTER une valeur. L'avertissement se
        # serait alors levé au moment d'enrichir la liste.
        origine = set(self._origin.value_ids.ids)
        saisies = set(self.value_ids._origin.ids)
        retirees = origine - saisies
        if not retirees:
            return None
        bloquees = self._origin.product_template_value_ids.filtered(
            lambda ptav: ptav.product_attribute_value_id.id in retirees
            and ptav.ptav_active
            and ptav._removal_would_archive()
        )
        if not bloquees:
            return None
        return {
            "warning": {
                "title": self.env._("These values will be deactivated"),
                "message": self.env._(
                    "%(values)s cannot be deleted: variants already use them. "
                    "They will be deactivated instead — past orders stay valid, "
                    "and the choice disappears from future configurations.",
                    values=", ".join(
                        bloquees.mapped("product_attribute_value_id.name")
                    ),
                ),
            }
        }

    @api.constrains("sale_separately", "attribute_id", "required")
    def _check_sale_separately(self):
        """Ce qu'une question vendue à part exige — et le refus DIT quoi faire (D-077)."""
        for line in self.filtered("sale_separately"):
            attribute = line.attribute_id
            # ⓘ D-371 : une question OBLIGATOIRE ne peut pas se trouver sur une ligne
            # séparée — une option se retire, et supprimer sa ligne du devis la désélectionne.
            if line.required:
                raise ValidationError(self.env._(
                    "“%s” cannot be sold separately while it is required: a part sold "
                    "separately is an option, which can be left out. Untick “Required” "
                    "first.", attribute.display_name))
            if "value_type" in attribute._fields and attribute.value_type != "product":
                raise ValidationError(self.env._(
                    "“%s” cannot be sold separately: its answers must designate products. "
                    "Set the attribute's value type to Product first.",
                    attribute.display_name))
            if attribute.create_variant != "no_variant":
                raise ValidationError(self.env._(
                    "“%s” cannot be sold separately while it creates variants: the answer "
                    "would be counted twice, once in this product and once on its own "
                    "line. Set the attribute's variant creation to “Never”.",
                    attribute.display_name))

    @api.constrains("attribute_id", "product_tmpl_id", "sale_separately", "dimension_role")
    def _check_no_variant_on_configurable(self):
        """Ce qu'une question « sans variante » n'a pas le droit d'être sur un produit
        CONFIGURABLE — W-99 / D-393.

        Sa réponse va sur la ligne de commande, pas dans l'article : deux configurations qui
        ne diffèrent que par elle sont le MÊME article. Deux choses ne le supportent pas :

        1. **un composant intégré** (des valeurs qui désignent des produits, non vendus à
           part) : la nomenclature est bâtie PAR ARTICLE et réutilisée — le composant serait
           perdu ou faux. Il crée des variantes, ou se vend à part (D-368) ;
        2. **un axe de grille de prix** : la grille se lit sur l'article (D-093), qui ne
           porterait plus la cote.
        """
        for line in self:
            attribute = line.attribute_id
            if not line.product_tmpl_id.config_ok or attribute.create_variant != "no_variant":
                continue
            if line.dimension_role:
                raise ValidationError(self.env._(
                    "“%s” cannot be a price grid axis while it creates no variant: the grid "
                    "is read on the configured product, which would not carry the dimension. "
                    "Set the attribute's variant creation to “Dynamically”.",
                    attribute.display_name))
            if attribute.value_type == "product" and not line.sale_separately:
                raise ValidationError(self.env._(
                    "“%s” designates components but creates no variant: two configurations "
                    "differing only by it would share one product, and one bill of "
                    "materials. Set its variant creation to “Dynamically”, or sell it "
                    "separately.", attribute.display_name))

    @api.constrains("dimension_role", "product_tmpl_id")
    def _check_dimension_role_unique(self):
        """Un rôle, un seul porteur par produit — sinon la grille ne sait plus
        quelle cote lire, et le choix se ferait par l'ordre des lignes."""
        for line in self.filtered("dimension_role"):
            twin = self.search(
                [
                    ("product_tmpl_id", "=", line.product_tmpl_id.id),
                    ("dimension_role", "=", line.dimension_role),
                    ("id", "!=", line.id),
                ],
                limit=1,
            )
            if twin:
                raise ValidationError(
                    self.env._(
                        "'%(attribute)s' already plays this role on %(product)s",
                        attribute=twin.attribute_id.display_name,
                        product=line.product_tmpl_id.display_name,
                    )
                )
            if not line.attribute_id._is_numeric_custom():
                raise ValidationError(
                    self.env._(
                        "Only a numeric attribute can carry a grid axis — "
                        "'%(attribute)s' is not one",
                        attribute=line.attribute_id.display_name,
                    )
                )

    @api.constrains("value_ids", "default_val")
    def _check_default_values(self):
        """default value should not be outside of the
        values selected in attribute line"""
        for line in self.filtered(lambda line: line.default_val):
            if line.default_val not in line.value_ids:
                raise ValidationError(
                    self.env._(
                        "Default values for each attribute line must exist in "
                        "the attribute values (%(attr_name)s: %(default_val)s)",
                        **{
                            "attr_name": line.attribute_id.name,
                            "default_val": line.default_val.name,
                        },
                    )
                )

    @api.constrains("active", "value_ids", "attribute_id")
    def _check_valid_values(self):
        """Overwrite to save attribute line without
        values when custom is true"""
        for ptal in self:
            # Customization
            if ptal.active and not ptal.value_ids and not ptal.custom:
                # Old code
                # if ptal.active and not ptal.value_ids:
                # Customization End
                raise ValidationError(
                    self.env._(
                        "The attribute %(attr)s must have at least one value for "
                        "the product %(product)s.",
                        **{
                            "attr": ptal.attribute_id.display_name,
                            "product": ptal.product_tmpl_id.display_name,
                        },
                    )
                )
            for pav in ptal.value_ids:
                if pav.attribute_id != ptal.attribute_id:
                    raise ValidationError(
                        self.env._(
                            "On the product %(product)s you cannot associate the "
                            "value %(value)s with the attribute %(attr)s because they "
                            "do not match.",
                            **{
                                "product": ptal.product_tmpl_id.display_name,
                                "value": pav.display_name,
                                "attr": ptal.attribute_id.display_name,
                            },
                        )
                    )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        # ⚠️ **UNE LIGNE DYNAMIQUE NAÎT AVEC LES VALEURS PROPOSÉES** — D-222.
        # Le cœur exige au moins une valeur par ligne (`_check_valid_values`) :
        # une ligne dynamique fraîche était donc IMPOSSIBLE à créer sans choisir
        # d'abord une valeur à la main — sur un attribut dont tout l'objet est de
        # ne pas tenir de liste.
        #
        # ⓘ On ne remplit QUE si rien n'est fourni : un appelant qui choisit ses
        # valeurs garde le dernier mot.
        attribut_obj = self.env["product.attribute"]
        for vals in vals_list:
            if vals.get("value_ids") or not vals.get("attribute_id"):
                continue
            attribut = attribut_obj.browse(vals["attribute_id"])
            if not attribut.dynamic_values:
                continue
            proposees = attribut._materialise_proposed_values()
            if proposees:
                vals["value_ids"] = [(6, 0, proposees.ids)]
        lines = super().create(vals_list)
        lines._ensure_config_step_lines()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if "config_step_id" in vals:
            self._ensure_config_step_lines()
        return res

    def action_open_configurator_line(self):
        """Ouvre les réglages de CETTE ligne — D-217.

        ⚠️ **SANS ELLE, ILS SONT INJOIGNABLES DEPUIS LA FICHE PRODUIT** : le bouton
        « Configurer » du cœur ouvre les **valeurs**
        (`action_open_attribute_values`), pas la ligne. Or c'est la ligne qui porte
        le mode de prix, le rôle de dimension, les bornes et la vue 3D — et c'est
        **elle** qui est lue à l'exécution, pas la semence de l'attribut.

        ⓘ Une seule porte pour tous ces réglages : le formulaire de la ligne
        existait déjà, complet ; il ne manquait qu'un chemin vers lui.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.attribute_id.display_name,
            "res_model": "product.template.attribute.line",
            "res_id": self.id,
            "view_mode": "form",
            # ⚠️ La vue du CŒUR : nos ajouts y sont greffés par héritage, et
            # nommer la vue héritée reviendrait à ignorer ceux des autres modules.
            # ⓘ `views` explicite parce que l'action part vers un composant (L-165).
            "views": [
                (self.env.ref("product.product_template_attribute_line_form").id,
                 "form"),
            ],
            "target": "new",
        }

    def action_open_values(self):
        """Ouvre les valeurs de CETTE ligne, dans un dialogue.

        ⚠️ Le domaine porte sur `attribute_line_id`, pas sur l'attribut : deux
        produits partagent un attribut mais jamais ses valeurs de produit, et
        filtrer sur l'attribut montrerait celles de tout le catalogue.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.attribute_id.display_name,
            "res_model": "product.template.attribute.value",
            "view_mode": "list",
            # ⚠️ Voir le commentaire de `configurator_open_condition` : hors
            # `call_button`, personne ne complète l'action, et le client lève
            # « Cannot read properties of undefined (reading 'map') ».
            "views": [(False, "list")],
            "domain": [("attribute_line_id", "=", self.id)],
            # ⓘ Sans `active_test=False`, une valeur DÉSACTIVÉE serait invisible —
            # or c'est précisément l'état où l'on vient voir ce qui s'est passé
            # (D-205), et le seul endroit d'où la réactiver.
            "context": {"active_test": False, **self._values_list_context()},
            "target": "new",
        }

    def action_open_attribute_values(self):
        """Le bouton « Configurer » du cœur ouvre la MÊME liste : même contexte."""
        action = super().action_open_attribute_values()
        action["context"] = {
            **action.get("context", {}),
            **self._values_list_context(),
        }
        return action

    # ─ LES VALEURS S'OUVRENT DANS UN DIALOGUE — B5, QE, D-206 ───────────────
    #
    # ⓘ **C'est le geste que le cœur d'Odoo emploie déjà** pour le même problème :
    # au-delà d'une poignée de valeurs, des pastilles `many2many_tags` deviennent
    # illisibles, et le cœur bascule sur une liste. La convergence est un bon
    # signe — ce n'est pas un contournement.
    #
    # ⚠️ **Un DIALOGUE et non une action pleine page**, à l'inverse du cœur : la
    # pleine page perd le contexte de l'arbre, qui est justement ce que l'onglet
    # apporte. On revient de la liste des valeurs là où on l'a ouverte.
    def _configurator_camera_name(self):
        """Le nom de la vue 3D de cette ligne — vide si l'éditeur n'est pas là.

        ⚠️ Le cœur du configurateur NE CONNAÎT PAS `view_camera_id` : le champ
        vient du pont, et l'exposer ici ferait dépendre l'AGPL-3 de l'éditeur —
        l'inverse du sens que D-075 protège. L'arbre a pourtant besoin d'une
        colonne. Ce crochet la remplit quand le pont est installé, et rend une
        chaîne vide sinon.
        """
        self.ensure_one()
        return ""

    def _configurator_camera_id(self):
        """L'identifiant de la vue 3D de cette ligne — `False` sans le pont (D-386).

        ⓘ Même crochet que `_configurator_camera_name`, pour la même raison : la
        colonne de l'arbre devient une LISTE DÉROULANTE, qui doit savoir quelle vue
        est choisie sans que le cœur connaisse `view_camera_id`.
        """
        self.ensure_one()
        return False

    def _configurator_set_camera(self, camera_id):
        """Poser la vue 3D de cette ligne — le pont l'écrit, le cœur ne sait pas."""
        raise UserError(self.env._("3D views need the 3D configurator module."))

    def _values_list_context(self):
        """Ce qui permet à la liste des valeurs de cacher une colonne ENTIÈRE.

        ⚠️ `column_invisible` ne lit pas les enregistrements, seulement le
        contexte : sans ces deux clés, seule la cellule se vide (`invisible`) et
        l'en-tête reste, au-dessus d'une colonne blanche. La liste ouverte d'une
        ligne ne porte qu'UN mode et UN type — c'est ce qui rend la colonne
        décidable. Ouverte d'ailleurs, sans ces clés, toutes les colonnes restent.
        """
        self.ensure_one()
        return {
            "configurator_price_mode": self.price_mode,
            "configurator_value_type": self.attribute_id.value_type,
            "configurator_display_type": self.attribute_id.display_type,
        }

    # ⚠️ MARQUER UNE ÉTAPE, C'EST LA DÉCLARER SUR LE PRODUIT. Les réglages d'une
    # étape — sa condition de visibilité (D-086) — vivent sur
    # `product.config.step.line`, un enregistrement par produit et par étape.
    # Poser le marqueur sans cet enregistrement donnerait une étape sans réglages
    # possibles, et l'assistant, qui itère sur `config_step_line_ids`, ne la
    # verrait même pas.
    #
    # ⓘ Ce n'est PAS un mirroir : cet enregistrement ne porte plus ni l'ordre ni
    # l'appartenance — les deux sont déduits. Il ne porte que ce qui appartient
    # en propre à l'étape sur ce produit.
    def _ensure_config_step_lines(self):
        step_line_obj = self.env["product.config.step.line"].sudo()
        for line in self.filtered(lambda l: l.config_step_id and l.product_tmpl_id):
            domaine = [
                ("product_tmpl_id", "=", line.product_tmpl_id.id),
                ("config_step_id", "=", line.config_step_id.id),
            ]
            if step_line_obj.search_count(domaine):
                continue
            # ⓘ `search_count` vide le tampon d'écriture du modèle avant de
            # chercher : une ligne d'étape créée plus tôt dans la même transaction
            # est donc vue. Et si un doublon passait quand même, `_check_config_step`
            # le refuse déjà, avec ses mots — inutile d'en ajouter d'autres.
            step_line_obj.create({
                "product_tmpl_id": line.product_tmpl_id.id,
                "config_step_id": line.config_step_id.id,
            })

    def _unavailable_display(self):
        """`grey` ou `hide` : ce que la page fait d'une valeur indisponible — D-168.

        ⓘ Le SEUL lecteur de la règle : la ligne si elle est réglée, sinon
        l'attribut, sinon le grisé — ce que la page a toujours fait.
        """
        self.ensure_one()
        return (self.unavailable_display
                or self.attribute_id.unavailable_display
                or "grey")

    def _is_visible(self, value_ids=None, custom_vals=None):
        """L'attribut est-il demandé pour cette configuration ? — D-086.

        ⚠️ C'est le niveau du MILIEU, celui qui n'existait pas. Aujourd'hui un
        attribut ne disparaît que par effet de bord — toutes ses valeurs
        écartées — et il en découle deux défauts : un attribut NUMÉRIQUE, qui
        n'a pas de valeurs, ne peut pas être masqué du tout ; et un masquage par
        effet de bord ne se LIT pas, donc l'utilisateur voit un attribut
        disparaître sans qu'aucune règle visible ne l'explique.
        """
        self.ensure_one()
        if not self.visibility_domain_id:
            return True
        session = self.env["product.config.session"]
        return session.validate_domains_against_sels(
            self.visibility_domain_id.compute_domain(),
            value_ids or [],
            custom_vals or {},
        )

    def _get_bounds(self, value_ids=None, custom_vals=None):
        """Rend les bornes applicables à cette ligne pour une configuration.

        La PREMIÈRE borne conditionnelle dont le domaine est satisfait gagne, et
        elle remplace les bornes par défaut ENTIÈREMENT — jamais champ par champ.
        Fusionner un maxi conditionnel avec un mini par défaut donnerait une règle
        que personne n'a écrite nulle part, et qui ne se lit dans aucun écran.
        Aucune ne correspond : les bornes portées par la ligne s'appliquent.

        ⚠️ Un domaine VIDE est satisfait — c'est la sémantique de
        `validate_domains_against_sels`, la même que pour les valeurs disponibles.
        """
        self.ensure_one()
        session = self.env["product.config.session"]
        for bound in self.bound_ids:
            domains = bound.domain_id.compute_domain()
            if session.validate_domains_against_sels(
                domains, value_ids or [], custom_vals or {}
            ):
                return bound.as_bounds(cause=bound.domain_id.name)
        return self.as_bounds()

    def _format_bound(self, value):
        """« 4000 mm » — une borne s'affiche comme la valeur qu'elle borne.

        Le formatage vit sur l'ATTRIBUT et pas ici : une borne, une saisie et
        une valeur rangée sont le même nombre vu à trois moments, et trois
        mises en forme finiraient par diverger.
        """
        self.ensure_one()
        return self.attribute_id.format_custom_value(value)

    @api.model
    def _bound_tolerance(self, *values):
        """Tolérance de comparaison — un flottant ne tombe jamais juste."""
        return max(abs(v) for v in (*values, 1.0)) * 1e-9

    def _suggest_val(self, val, bounds):
        """La valeur admissible la plus proche, ou `None` s'il n'en existe pas.

        C'est la moitié « en PROPOSANT » de D-077 : refuser sans montrer le seul
        chemin enferme l'utilisateur dans un ordre imposé qu'il doit deviner.
        """
        minv, maxv, step = bounds["min_val"], bounds["max_val"], bounds["step"]
        suggestion = val
        if minv is not None and suggestion < minv:
            suggestion = minv
        if maxv is not None and suggestion > maxv:
            suggestion = maxv
        if step:
            base = minv if minv is not None else 0.0
            suggestion = base + round((suggestion - base) / step) * step
            tol = self._bound_tolerance(suggestion, step)
            # Le pas peut faire sortir des bornes : on rentre, on ne sort jamais.
            if minv is not None and suggestion < minv - tol:
                suggestion += step
            if maxv is not None and suggestion > maxv + tol:
                suggestion -= step
        return None if self._bounds_error(suggestion, bounds) else suggestion

    def _bounds_error(self, val, bounds):
        """Rend le message d'erreur, ou `None` si la valeur passe.

        Rendre un message plutôt que lever laisse l'interface DEMANDER si une
        valeur passe — le dialogue de D-077 a besoin de le savoir avant que
        l'utilisateur ne valide, pas après.
        """
        self.ensure_one()
        minv, maxv, step = bounds["min_val"], bounds["max_val"], bounds["step"]
        name = self.attribute_id.name
        tol = self._bound_tolerance(val, minv or 0.0, maxv or 0.0, step or 0.0)
        message = None
        if minv is not None and val < minv - tol:
            message = self.env._(
                "Custom value %(val)s for '%(name)s' is below the minimum "
                "of %(min_val)s.",
                val=self._format_bound(val),
                name=name,
                min_val=self._format_bound(minv),
            )
        elif maxv is not None and val > maxv + tol:
            message = self.env._(
                "Custom value %(val)s for '%(name)s' is above the maximum "
                "of %(max_val)s.",
                val=self._format_bound(val),
                name=name,
                max_val=self._format_bound(maxv),
            )
        elif step:
            base = minv if minv is not None else 0.0
            offset = abs((val - base) % step)
            if offset > tol and abs(offset - step) > tol:
                message = self.env._(
                    "Custom value %(val)s for '%(name)s' must go by steps "
                    "of %(step)s from %(base)s.",
                    val=self._format_bound(val),
                    name=name,
                    step=self._format_bound(step),
                    base=self._format_bound(base),
                )
        if message is None:
            return None
        if bounds.get("cause"):
            message += " " + self.env._(
                "This limit comes from condition '%(cause)s'.",
                cause=bounds["cause"],
            )
        suggestion = self._suggest_val(val, bounds)
        if suggestion is not None:
            message += " " + self.env._(
                "Nearest allowed value: %(suggestion)s.",
                suggestion=self._format_bound(suggestion),
            )
        return message

    def resolve_custom_value(self, raw):
        """Rend la valeur d'une saisie — nombre ou texte — et l'ATTACHE à cette ligne.

        ⚠️ Sans l'attachement, la valeur n'aurait pas de ptav : aucune variante ne la
        porterait, et le stock resterait aveugle (D-081, D-353).
        ⚠️ `sudo()` : celui qui configure n'a pas le droit d'écrire sur le produit, et
        il ne doit pas l'avoir.
        """
        self.ensure_one()
        value = self.attribute_id.resolve_custom_value(raw)
        if value and value not in self.value_ids:
            self.sudo().write({"value_ids": [(4, value.id)]})
        return value

    def offered_value_for(self, raw):
        """La valeur DÉJÀ OFFERTE par cette ligne que la saisie désigne — ou rien.

        ⓘ Taper « 18 » quand « 18 » est dans la liste n'est pas un ajout, c'est un
        CHOIX (D-353) : la saisie se range alors comme un clic sur la valeur, et
        rien de neuf n'attend la confirmation.
        """
        self.ensure_one()
        return self.attribute_id.find_custom_value(raw, values=self.value_ids)

    def validate_custom_val(self, val, value_ids=None, custom_vals=None):
        """Refuse une saisie hors bornes, hors format ou trop longue.

        D-077, et sur la LIGNE, D-089 : bornes et pas d'un nombre. D-353 : longueur
        maxi et expression régulière d'un texte — jusqu'ici tenues par le seul
        navigateur de l'éditeur, alors que la page du configurateur est PUBLIQUE.

        ⚠️ Le configurateur REFUSE là où le moteur borne (D-040 B) : il traite
        une saisie humaine, dont la valeur engage une commande.

        ⚠️ **Un nombre se lit par `parse_number`, jamais par `literal_eval`** : la
        seconde refuse « 2,5 », ce que tape un clavier français ([[L-218]]).
        """
        self.ensure_one()
        attribute = self.attribute_id
        if attribute.is_numeric():
            number = attribute.parse_number(val)
            if number is None:
                raise ValidationError(
                    self.env._(
                        "'%(val)s' is not a number for '%(name)s'.",
                        val=val,
                        name=attribute.name,
                    )
                )
            message = self._bounds_error(number, self._get_bounds(value_ids, custom_vals))
            if message:
                raise ValidationError(message)
            return
        if attribute.value_type != "value":
            return
        if attribute.is_ranges():
            # ⓘ W-102 — des plages notées comme l'impression de pages ; la lecture et le
            # message vivent dans `product_attribute_advanced`, avec le format.
            message = attribute.ranges_error(val)
            if message:
                raise ValidationError(message)
        text = attribute.normalize_custom_text(val)
        if self.max_length and len(text) > self.max_length:
            raise ValidationError(
                self.env._(
                    "'%(name)s' accepts at most %(count)s characters.",
                    name=attribute.name,
                    count=self.max_length,
                )
            )
        if self.regexp and text:
            try:
                accepted = re.fullmatch(self.regexp, text)
            except re.error:
                # ⓘ Un motif mal écrit est une faute de l'AUTEUR : la reprocher au
                # client le bloquerait sans rien qu'il puisse corriger.
                _logger.warning(
                    "Invalid accepted format %r on line %s: ignored", self.regexp, self.id
                )
                accepted = True
            if not accepted:
                raise ValidationError(
                    self.env._(
                        "'%(val)s' does not have the format expected for '%(name)s'.",
                        val=text,
                        name=attribute.name,
                    )
                )

    def _configurator_value_ids(self):
        """Values accepted for template attribute lines in `self`.

        ⚠️ **SUR UN ATTRIBUT DYNAMIQUE, C'EST LE FILTRE QUI ALIMENTE** — C3,
        D-221. La liste de la ligne cesse alors d'être un catalogue à tenir pour
        devenir la **trace** de ce qui a été choisi (QJ).

        ⓘ On rend l'UNION, jamais le seul filtre : une valeur déjà retenue doit
        rester offerte même si le filtre a changé depuis — sinon une
        configuration en cours perdrait son choix, et une reconfiguration
        deviendrait impossible.

        ⚠️ **LE SEUL point « valeurs offertes »** : le domaine de l'assistant passe
        par ICI, pas par la construction de la vue — une seconde méthode divergerait
        au premier appelant oublié (D-221).
        """
        values = self.value_ids
        for line in self.filtered(lambda l: l.attribute_id.dynamic_values):
            values |= line.attribute_id._materialise_proposed_values()
        if any(self.mapped("custom")):
            values += self.env["product.config.session"].get_custom_value_id()
        return values
