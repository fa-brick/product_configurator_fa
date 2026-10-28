"""Ce qu'exécute `product.template` (BLL, D-541)."""
from odoo import models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ─ L'ARBRE DU CONFIGURATEUR, TEL QUE L'ÉCRAN LE LIT — D-210 ─────────────
    #
    # ⓘ Un arbre où l'étape est un bandeau, l'attribut une ligne, et ses valeurs des
    # lignes indentées portant chacune leur condition.
    # ⚠️ Une liste Odoo ne sait ni s'imbriquer ni mêler trois modèles : le composant lit
    # UNE structure, au lieu de recomposer côté client une jointure (D-210).
    # ⚠️ L'ÉTAPE est un bandeau RENDU, pas un enregistrement : elle reste un marqueur porté
    # par la ligne qui l'ouvre (D-202).
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

        etapes = {sl.config_step_id: sl for sl in self.config_step_line_ids}
        for ligne in self.attribute_line_ids.sorted():
            if ligne.config_step_id and ligne.config_step_id != ouverte:
                ouverte = ligne.config_step_id
                # ⓘ La vue 3D de l'étape vit sur SA ligne d'étape (`step.line`), pas
                # sur `product.config.step`, partagé entre produits (D-386).
                etape = etapes.get(ligne.config_step_id)
                lignes.append({
                    "kind": "step",
                    "id": ligne.config_step_id.id,
                    "line_id": ligne.id,
                    "name": ligne.config_step_id.display_name,
                    "camera": etape._configurator_camera_name() if etape else "",
                    "camera_id": etape._configurator_camera_id() if etape else False,
                })
            lignes.append({
                "kind": "attribute",
                "id": ligne.id,
                "name": ligne.attribute_id.display_name,
                "facets": ligne.visibility_domain_id._facet_data(),
                "domain_id": ligne.visibility_domain_id.id,
                "camera": ligne._configurator_camera_name(),
                "camera_id": ligne._configurator_camera_id(),
                # ⓘ D-368 — la question donne une ligne de devis À PART.
                "sale_separately": bool(ligne.sale_separately),
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

    # ─ LA VUE 3D, CHOISIE DANS L'ARBRE — D-386 ─────────────────────────────
    #
    # ⓘ Une liste déroulante par attribut ET par bandeau d'étape (D-386).
    # ⚠️ Le cœur ne connaît pas les caméras : il demande les choix et délègue l'écriture
    # au pont (D-163).
    def _configurator_camera_choices(self):
        """Les vues 3D qu'on peut choisir pour ce produit — aucune sans le pont."""
        self.ensure_one()
        return []

    def configurator_camera_choices(self):
        """`[{id, name}]` — la liste déroulante de la colonne « Vue 3D »."""
        self.ensure_one()
        return self._configurator_camera_choices()

    def configurator_set_camera(self, kind, record_id, camera_id):
        """Pose la vue 3D d'un ATTRIBUT (`kind="attribute"`, ligne d'attribut) ou d'une
        ÉTAPE (`kind="step"`, `product.config.step`) — `camera_id` faux l'efface.

        ⚠️ La cible est cherchée PARMI CELLES DU PRODUIT : sans cette garde, l'arbre
        d'un produit pourrait écrire sur la ligne d'un autre.
        """
        self.ensure_one()
        if kind == "step":
            cible = self.config_step_line_ids.filtered(
                lambda sl: sl.config_step_id.id == record_id
            )[:1]
        else:
            cible = self.attribute_line_ids.filtered(lambda l: l.id == record_id)
        if not cible:
            raise UserError(self.env._("This line does not belong to this product."))
        cible._configurator_set_camera(camera_id or False)
        return True

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
        CAPACITÉ** : c'est d'ici, et d'ici seulement, que l'arbre crée une condition
        PAR VALEUR (D-213).

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
        # ⓘ **LE DIALOGUE EST CELUI DE LA BARRE DE RECHERCHE** (D-224).
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

    # ─ POSER UNE ÉTAPE COMME ON POSE UNE SECTION ────────────────────────────
    #
    # ⓘ Le geste des lignes de commande : une ligne se crée, on la nomme, puis on la
    # déplace à sa position.
    # ⚠️ Une étape reste un MARQUEUR porté par la ligne qui l'ouvre (D-202) : elle ne
    # peut pas se poser sous la dernière ligne. On la pose sur la DERNIÈRE LIGNE LIBRE.
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

    def configurator_reorder(self, line_ids, step_line_ids=None):
        """Réordonne les lignes d'attribut — l'ordre PORTE l'appartenance.

        ⚠️ Déplacer une ligne peut changer son étape (D-202), en silence. C'est
        assumé ; c'est pourquoi l'arbre redessine ses bandeaux après chaque
        déplacement, au lieu d'attendre un rechargement.

        ⚠️ **SANS `step_line_ids`, LE MARQUEUR SUIT SA LIGNE** : la ligne qui ouvre
        une étape ne pourrait pas passer au-dessus de son propre bandeau. L'arbre
        envoie donc aussi la ligne que chaque étape ouvre (paires
        ``[step_id, line_id]``).
        ⚠️ Les deux s'écrivent ENSEMBLE : un état intermédiaire ouvrirait une étape
        sur la mauvaise ligne.
        """
        self.ensure_one()
        lignes = self.env["product.template.attribute.line"].browse(line_ids)
        for rang, ligne in enumerate(lignes, start=1):
            ligne.sequence = rang * 10
        if step_line_ids:
            self._configurator_place_steps(step_line_ids)
        return True

    def _configurator_place_steps(self, step_line_ids):
        """Pose chaque étape sur la ligne donnée — paires ``[step_id, line_id]``.

        ⚠️ Seules les étapes DÉJÀ ouvertes sur ce produit se déplacent : sans
        cette garde, l'arbre d'un produit pourrait y poser n'importe quelle étape
        du catalogue. Et une ligne n'ouvre qu'UNE étape : une cible qui en porte
        une autre, absente de la liste, la perdrait sans le dire.
        """
        placees = dict(step_line_ids)
        if len(set(placees.values())) != len(placees):
            raise UserError(self.env._("An attribute can open only one step."))
        etapes = self.env["product.config.step"].browse(list(placees))
        if etapes - self.attribute_line_ids.config_step_id:
            raise UserError(
                self.env._("This step is not declared on this product.")
            )
        cibles = self.env["product.template.attribute.line"].browse(
            list(placees.values())
        )
        if cibles - self.attribute_line_ids:
            raise UserError(
                self.env._("This attribute line does not belong to this product.")
            )
        autres = cibles.config_step_id - etapes
        if autres:
            raise UserError(
                self.env._(
                    "“%(other)s” already opens on this attribute. Move it first.",
                    other=autres[:1].name,
                )
            )
        # ⓘ Effacer d'abord, poser ensuite : une ligne peut perdre une étape et
        # en recevoir une autre dans le même appel.
        self.attribute_line_ids.filtered(
            lambda ligne: ligne.config_step_id in etapes
        ).config_step_id = False
        for etape_id, line_id in placees.items():
            cibles.browse(line_id).config_step_id = etape_id

    def configurator_reorder_values(self, line_id, value_ids):
        """Réordonne les VALEURS d'un attribut — l'ordre est celui de l'attribut.

        ⚠️ **CET ORDRE EST GLOBAL, ET C'EST ASSUMÉ.** Une valeur est un
        `product.attribute.value` : son rang vit dans sa `sequence`, qui
        appartient à l'ATTRIBUT et non au produit (`_order` du cœur :
        *attribute_id, sequence, id*). Déplacer « brut » depuis un produit le
        déplace donc partout où l'attribut sert — dans les autres produits comme
        dans Configuration → Attributs. C'est le seul ordre qui existe : en
        inventer un par produit obligerait tout ce qui affiche des valeurs à le
        relire.

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
