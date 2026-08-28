"""Écrire une condition dans le dialogue de la barre de recherche.

Demande de Gerry (2026-08-29) : *« quand on clique sur add a condition je
voulais retrouver la même fenêtre que pour les filtres de la barre de
recherche »*.

⚠️ **CES COUTURES VISENT LES DEUX APPELS QUE LE CLIENT FAIT VRAIMENT** —
`fields_get` sur le modèle-sujet, et `search_count` pendant la frappe. C'est
précisément là que le montage précédent échouait pendant que ses tests
passaient : ils éprouvaient une méthode que l'écran n'appelait jamais.
"""
from odoo.exceptions import UserError, ValidationError

from odoo.addons.base.tests.common import BaseCommon


class ConditionDialog(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attr_montage = cls.env["product.attribute"].create(
            {"name": "Mounting dlg", "create_variant": "no_variant"}
        )
        cls.avant = cls.env["product.attribute.value"].create(
            {"name": "Front", "attribute_id": cls.attr_montage.id}
        )
        cls.arriere = cls.env["product.attribute.value"].create(
            {"name": "Rear", "attribute_id": cls.attr_montage.id}
        )
        cls.etranger = cls.env["product.attribute"].create(
            {"name": "Not on this product", "create_variant": "no_variant"}
        )
        cls.env["product.attribute.value"].create(
            {"name": "Nope", "attribute_id": cls.etranger.id}
        )
        cls.template = cls.env["product.template"].create(
            {"name": "Dialog door", "config_ok": True}
        )
        cls.ligne = cls.env["product.template.attribute.line"].create({
            "product_tmpl_id": cls.template.id,
            "attribute_id": cls.attr_montage.id,
            "value_ids": [(6, 0, (cls.avant | cls.arriere).ids)],
        })

    def _assistant(self):
        action = self.template.configurator_open_condition(self.ligne.id)
        return self.env[action["res_model"]].browse(action["res_id"])

    def test_01_le_dialogue_s_ouvre_sur_la_condition_EXISTANTE(self):
        """Il arrive rempli, sinon rouvrir une condition l'effacerait."""
        self.ligne.visibility_domain_id = self.env["product.config.domain"].create({
            "name": "Rear only",
            "domain_line_ids": [(0, 0, {
                "attribute_id": self.attr_montage.id,
                "condition": "in",
                "value_ids": [(6, 0, self.arriere.ids)],
            })],
        })
        assistant = self._assistant()
        self.assertEqual(
            assistant.condition_domain,
            str([(f"__attribute_{self.attr_montage.id}", "in", self.arriere.ids)]),
        )

    def test_02_confirmer_REECRIT_la_condition(self):
        assistant = self._assistant()
        assistant.condition_domain = str(
            [(f"__attribute_{self.attr_montage.id}", "in", self.avant.ids)]
        )
        assistant.action_confirm()
        ligne_condition = self.ligne.visibility_domain_id.domain_line_ids
        self.assertEqual(ligne_condition.attribute_id, self.attr_montage)
        self.assertEqual(ligne_condition.value_ids, self.avant)

    def test_03_le_selecteur_ecrit_EGAL_le_stockage_lit_DANS(self):
        """⚠️ Choisir un champ dans l'éditeur produit `('champ', '=', id)` —

        c'est son défaut pour un `many2one`. Refuser sec rendait le dialogue
        hostile : on désigne un attribut, et l'enregistrement échoue sans qu'on
        ait rien fait de faux.
        """
        assistant = self._assistant()
        assistant.condition_domain = str(
            [(f"__attribute_{self.attr_montage.id}", "=", self.arriere.id)]
        )
        assistant.action_confirm()
        ligne_condition = self.ligne.visibility_domain_id.domain_line_ids
        self.assertEqual(ligne_condition.condition, "in")
        self.assertEqual(ligne_condition.value_ids, self.arriere)

    def test_04_mais_NON_DEFINI_reste_refuse(self):
        """Une valeur absente n'est pas une valeur à écarter — le stockage ne

        sait pas l'exprimer, et l'accepter en douce serait la perdre.
        """
        assistant = self._assistant()
        assistant.condition_domain = str(
            [(f"__attribute_{self.attr_montage.id}", "=", False)]
        )
        with self.assertRaises(ValidationError):
            assistant.action_confirm()

    def test_05_un_attribut_ETRANGER_au_produit_est_refuse_avec_ses_mots(self):
        """⚠️ Le modèle-sujet offre TOUS les attributs configurables — il n'a pas

        de contexte pour les restreindre à ce produit-ci. Une condition sur un
        attribut absent ne pourrait jamais être vraie : mieux vaut le dire que
        de laisser une règle morte.
        """
        self.env["product.template.attribute.line"].create({
            "product_tmpl_id": self.env["product.template"].create(
                {"name": "Other configurable", "config_ok": True}
            ).id,
            "attribute_id": self.etranger.id,
            "value_ids": [(6, 0, self.etranger.value_ids.ids)],
        })
        assistant = self._assistant()
        assistant.condition_domain = str(
            [(f"__attribute_{self.etranger.id}", "in", self.etranger.value_ids.ids)]
        )
        with self.assertRaises(UserError):
            assistant.action_confirm()

    def test_06_le_MODELE_SUJET_offre_les_attributs_configurables(self):
        """Le premier des deux appels que le client fait vraiment."""
        champs = self.env["product.config.condition.subject"].fields_get()
        self.assertIn(f"__attribute_{self.attr_montage.id}", champs)

    def test_07_et_un_attribut_que_RIEN_ne_configure_n_est_pas_offert(self):
        """ⓘ Il ne peut apparaître dans aucune configuration : le proposer

        serait offrir d'écrire une règle qui ne peut pas se déclencher.
        """
        orphelin = self.env["product.attribute"].create(
            {"name": "Unused attribute", "create_variant": "no_variant"}
        )
        champs = self.env["product.config.condition.subject"].fields_get()
        self.assertNotIn(f"__attribute_{orphelin.id}", champs)

    def test_08_chaque_champ_offert_porte_sa_cle_name(self):
        """⚠️ **La couture qui manquait, et qui a coûté un aller-retour.**

        Le sélecteur de champ compose le chemin retenu avec `fieldDef.name`, pas
        avec la clé du dictionnaire (`model_field_selector_popover.js`). Sans
        cette clé, choisir un attribut posait un chemin `undefined` — *« Chaîne
        de champs invalide »*, puis *« Domaine invalide »*. Le dialogue
        s'ouvrait, listait bien les attributs, et refusait toute saisie.

        ⓘ Un `fields_get` fabriqué à la main doit rendre les MÊMES clés que le
        vrai : c'est un contrat, pas une commodité.
        """
        champs = self.env["product.config.condition.subject"].fields_get()
        obligatoires = set(
            self.env["product.product"].fields_get(["id"])["id"].keys()
        ) & {"name", "string", "type", "searchable", "store"}
        for cle, definition in champs.items():
            self.assertEqual(definition.get("name"), cle, cle)
            self.assertFalse(obligatoires - set(definition), cle)

    def test_09_seuls_les_ATTRIBUTS_sont_offerts(self):
        """Le sujet d'une condition est un attribut — pas « créé le », pas « ID ».

        ⓘ Laissés là, les champs techniques encombraient la liste et
        fournissaient même la règle par défaut (« ID = 1 »).
        """
        champs = self.env["product.config.condition.subject"].fields_get()
        self.assertTrue(champs)
        self.assertTrue(all(c.startswith("__") for c in champs), sorted(champs))
