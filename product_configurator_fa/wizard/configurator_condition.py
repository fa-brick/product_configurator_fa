"""Écrire une condition dans le MÊME dialogue que les filtres de la barre de
recherche — demande de Gerry (2026-08-29).

⚠️ **POURQUOI UN MODÈLE-SUJET, ET PAS `product.template`.** L'éditeur de domaine
charge ses champs par le service `field` du client, qui appelle `fields_get`
**sans contexte** et met le résultat en cache **par modèle seul**
(`web/static/src/core/field_service.js`). Deux conséquences, l'une fatale :

  · aucun contexte ne parvient à `fields_get` — les champs fictifs d'un produit
    donné ne pouvaient donc **jamais** apparaître ;
  · le cache étant indexé par modèle, les champs d'un produit auraient de toute
    façon fuité vers l'éditeur d'un autre.

ⓘ D'où ce modèle **dédié**, dont les champs ne dépendent que du catalogue
d'attributs — donc identiques pour tout le monde, donc cachables sans risque. Et
la pollution reste chez lui : déclarer ces champs sur `product.template` les
aurait fait surgir dans ses vues, ses exports et ses filtres, où plus rien ne
saurait les lire.
"""
from ast import literal_eval

from odoo import api, fields, models
from odoo.exceptions import UserError


class ProductConfigConditionSubject(models.TransientModel):
    """Le SUJET d'une condition : un attribut, jamais autre chose (D-080)."""

    _name = "product.config.condition.subject"
    _description = "Subject of a configuration condition"

    @api.model
    def _condition_attributes(self):
        """Les attributs qu'une condition peut tester.

        ⓘ Ceux qui servent à **au moins un produit configurable** — pas le
        catalogue entier : un attribut que rien ne configure ne peut apparaître
        dans aucune configuration, donc aucune condition ne peut le tester.
        """
        lignes = self.env["product.template.attribute.line"].search(
            [("product_tmpl_id.config_ok", "=", True)]
        )
        return lignes.attribute_id

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """Tolère les champs fictifs dans une recherche — sinon l'éditeur casse.

        ⚠️ L'éditeur de domaine COMPTE les enregistrements correspondants à
        chaque frappe. Sur des champs qui n'existent pas en base, ce décompte
        lève — et le widget affiche alors *« Domaine invalide »* et refuse la
        saisie. Le compteur lui-même n'a aucun sens ici (le modèle ne porte pas
        de données) : il est masqué, mais la requête part quand même.

        ⓘ Les feuilles fictives sont donc neutralisées, pas interprétées : ce
        n'est PAS ici qu'une condition s'évalue — c'est
        `validate_domains_against_sels`, contre une configuration en cours.
        """
        domaine_obj = self.env["product.config.domain"]
        prefixes = (
            domaine_obj.ATTRIBUTE_FIELD_PREFIX,
            domaine_obj.PRODUCT_FIELD_PREFIX,
        )
        nettoye = [
            (1, "=", 1)
            if not isinstance(feuille, str)
            and str(feuille[0]).startswith(prefixes)
            else feuille
            for feuille in domain
        ]
        return super()._search(nettoye, offset=offset, limit=limit, order=order)

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        champs = super().fields_get(allfields=allfields, attributes=attributes)
        domaine_obj = self.env["product.config.domain"]
        for attribut in self._condition_attributes():
            # ⚠️ TOUT attribut est décrit en `many2one` vers une VALEUR, y
            # compris les numériques — le stockage ne connaît que `in` / `not in`
            # sur des valeurs (D-080). Décrire une dimension en `float`
            # laisserait écrire `largeur > 4000`, que l'enregistrement perdrait
            # en silence.
            champs[domaine_obj._attribute_field_name(attribut)] = {
                "string": attribut.name,
                "type": "many2one",
                "relation": "product.attribute.value",
                "domain": [("attribute_id", "=", attribut.id)],
                "searchable": True,
                "sortable": False,
                "store": False,
                "readonly": False,
            }
            # C4, D-201 — un attribut de type produit se teste aussi par ses
            # produits. En PLUS, jamais à la place.
            if attribut.value_type == "product":
                champs[domaine_obj._product_field_name(attribut)] = {
                    "string": self.env._(
                        "%(attribute)s (products)", attribute=attribut.name
                    ),
                    "type": "many2one",
                    "relation": "product.product",
                    "searchable": True,
                    "sortable": False,
                    "store": False,
                    "readonly": False,
                }
        return champs


class ProductConfiguratorCondition(models.TransientModel):
    _name = "product.configurator.condition"
    _description = "Edit a configuration condition"

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template", required=True, readonly=True
    )
    domain_id = fields.Many2one(
        comodel_name="product.config.domain", required=True, readonly=True
    )
    subject = fields.Char(
        compute="_compute_subject",
        string="Applies to",
        help="What this condition governs.",
    )
    condition_domain = fields.Char(string="Condition", default="[]")

    @api.depends("domain_id")
    def _compute_subject(self):
        for assistant in self:
            assistant.subject = assistant.domain_id.display_name

    @api.model
    def open_for(self, product_tmpl, domain):
        """L'action qui ouvre le dialogue, prête à l'emploi.

        ⚠️ `views` EST OBLIGATOIRE : rendue à un composant par un appel ORM,
        l'action n'est complétée par personne — le client ferait
        `action.views.map(...)` sur `undefined` ([[L-165]]).
        """
        assistant = self.create({
            "product_tmpl_id": product_tmpl.id,
            "domain_id": domain.id,
            "condition_domain": str(domain.to_odoo_domain()),
        })
        formulaire = self.env.ref(
            "product_configurator_fa.product_configurator_condition_form_view"
        )
        return {
            "type": "ir.actions.act_window",
            "name": domain.display_name,
            "res_model": self._name,
            "res_id": assistant.id,
            "view_mode": "form",
            "views": [(formulaire.id, "form")],
            "target": "new",
        }

    def action_confirm(self):
        """Réécrit la condition depuis le domaine saisi.

        ⓘ `from_odoo_domain` refuse déjà ce que le stockage perdrait (D-080).
        Ici s'ajoute la seule vérification qu'il ne peut pas faire : l'attribut
        testé doit appartenir AU PRODUIT — le modèle-sujet offre tous les
        attributs configurables, faute de contexte pour les restreindre.
        """
        self.ensure_one()
        domaine = literal_eval(self.condition_domain or "[]")
        connus = self.product_tmpl_id.attribute_line_ids.attribute_id
        domaine_obj = self.env["product.config.domain"]
        for feuille in domaine:
            if isinstance(feuille, str):
                continue
            nom = str(feuille[0])
            for prefixe in (
                domaine_obj.PRODUCT_FIELD_PREFIX,
                domaine_obj.ATTRIBUTE_FIELD_PREFIX,
            ):
                if nom.startswith(prefixe):
                    attribut = self.env["product.attribute"].browse(
                        int(nom[len(prefixe):])
                    )
                    if attribut not in connus:
                        raise UserError(
                            self.env._(
                                "“%(attribute)s” is not an attribute of "
                                "“%(product)s”: a condition on it could never "
                                "be true. Add the attribute to the product "
                                "first.",
                                attribute=attribut.name,
                                product=self.product_tmpl_id.display_name,
                            )
                        )
                    break
        self.domain_id.from_odoo_domain(domaine)
        return {"type": "ir.actions.act_window_close"}
