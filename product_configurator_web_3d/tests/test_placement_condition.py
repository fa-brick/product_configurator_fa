# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La condition d'un EMPLACEMENT, écrite dans le dialogue du configurateur — D-267.

Demande de Gerry (2026-09-07) : *« à l'instar des conditions dans configurator, il
serait également possible dans cette dialogue de définir les conditions de visibilité de
l'emplacement »* — et *« on reprend le même à l'identique ainsi que ses contraintes »*.

Ce qui est éprouvé ici est la JONCTION : deux grammaires qui partagent leur vocabulaire,
et ce que la traduction refuse plutôt que de le perdre.
"""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.product_configurator_web_3d.models.placement_condition import (
    clauses_to_domain, domain_to_clauses, merge_clauses,
)
from odoo.addons.product_editor.models.product_attribute import ATTRIBUTE_SCOPE_PREFIX
from odoo.addons.product_configurator_fa.models.product_config import ProductConfigDomain


class TestPlacementCondition(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.produit = cls.env["product.template"].create(
            {"name": "Portail", "type": "consu", "config_ok": True})
        cls.attribut = cls.env["product.attribute"].create(
            {"name": "Montage", "create_variant": "no_variant"})
        cls.valeurs = cls.env["product.attribute.value"].create([
            {"name": "Ressort avant", "attribute_id": cls.attribut.id},
            {"name": "Ressort arrière", "attribute_id": cls.attribut.id},
        ])
        cls.env["product.template.attribute.line"].create({
            "product_tmpl_id": cls.produit.id,
            "attribute_id": cls.attribut.id,
            "value_ids": [(6, 0, cls.valeurs.ids)],
        })
        cls.assemblage = cls.env["product.model3d"].create({
            "name": "Portail", "piece_type": "assembly",
            "product_tmpl_id": cls.produit.id,
        })
        cls.enfant = cls.env["product.model3d"].create({"name": "Barreau"})
        cls.lien = cls.env["product.model3d.component"].create({
            "parent_id": cls.assemblage.id, "child_id": cls.enfant.id})
        cls.champ = "%s%s" % (ATTRIBUTE_SCOPE_PREFIX, cls.attribut.id)
        # Une question NUMÉRIQUE : sa réponse est saisie, pas cochée.
        # ⓘ Ce qui rend une question NUMÉRIQUE est son FORMAT (`custom_type`), pas ce
        # que ses valeurs désignent (`value_type`) : « 2,5 mm » reste un libellé qui ne
        # désigne que lui-même.
        cls.attribut_nombre = cls.env["product.attribute"].create({
            "name": "Épaisseur", "create_variant": "no_variant",
            "custom_type": "float",
        })
        cls.nombre = "%s%s" % (ATTRIBUTE_SCOPE_PREFIX, cls.attribut_nombre.id)

    # ── LE VOCABULAIRE PARTAGÉ ───────────────────────────────────────────

    def test_les_deux_cotes_nomment_un_attribut_PAREIL(self):
        """⚠️ C'est ce qui rend la traduction possible — et ce serait indétectable si
        l'un des deux préfixes changeait : les conditions deviendraient simplement
        inévaluables, sans une erreur."""
        self.assertEqual(ATTRIBUTE_SCOPE_PREFIX, ProductConfigDomain.ATTRIBUTE_FIELD_PREFIX)

    def test_une_clause_devient_une_feuille_et_revient_identique(self):
        presence = {"mode": "condition",
                    "all": [{"attr": self.champ, "op": "in", "values": self.valeurs.ids}]}
        domaine = clauses_to_domain(presence)
        self.assertEqual(domaine, [(self.champ, "in", self.valeurs.ids)])
        self.assertEqual(self._lire(domaine), presence["all"])

    # ── CE QUE LA TRADUCTION REFUSE ──────────────────────────────────────

    def test_le_OU_entre_deux_questions_devient_un_GROUPE(self):
        """⚠️ La grammaire est celle de la barre de recherche — ET entre les groupes, OU
        à l'intérieur (arbitrage Gerry, 2026-09-07) : la même des deux côtés, pour qu'on
        n'ait pas à changer de façon de penser en changeant d'écran."""
        domaine = ["|", (self.champ, "in", [1]), (self.champ, "in", [2])]
        groupes = self.env["product.config.domain"]._parse_condition_groups(domaine)
        elements = domain_to_clauses(domaine, groupes)
        self.assertEqual(len(elements), 1)
        self.assertEqual([c["values"] for c in elements[0]["any"]], [[1], [2]])

    def test_un_groupe_repart_en_domaine_PRÉFIXÉ(self):
        presence = {"mode": "condition", "all": [
            {"any": [{"attr": self.champ, "op": "in", "values": [1]},
                     {"attr": self.champ, "op": "in", "values": [2]}]}]}
        self.assertEqual(clauses_to_domain(presence),
                         ["|", (self.champ, "in", [1]), (self.champ, "in", [2])])

    def test_le_MELANGE_et_dans_ou_est_refuse_par_la_LECTURE_du_configurateur(self):
        """ⓘ Le refus n'est pas le nôtre : on emprunte `_parse_condition_groups`, donc
        ses règles ET ses mots. Deux lectures d'une même grammaire finiraient par
        accepter d'un côté ce que l'autre refuse."""
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env["product.config.domain"]._parse_condition_groups(
                ["|", (self.champ, "in", [1]), "&", (self.champ, "in", [2]),
                 (self.champ, "in", [3])])

    def test_le_OU_entre_VALEURS_d_une_meme_question_passe(self):
        """ⓘ C'est celui qu'on emploie le plus souvent — « montage parmi ces trois
        valeurs » —, et c'est UNE feuille des deux côtés."""
        clauses = self._lire([(self.champ, "in", self.valeurs.ids)])
        self.assertEqual(clauses[0]["values"], self.valeurs.ids)

    def test_le_selecteur_ecrit_EGAL_et_le_moteur_lit_DANS(self):
        """⚠️ Désigner une question dans l'éditeur produit `('champ', '=', id)` — le
        défaut du widget pour un many2one. Refuser sec rendrait le dialogue hostile :
        on n'a rien fait de faux. C'est la traduction que le configurateur fait déjà."""
        clauses = self._lire([(self.champ, "=", self.valeurs[0].id)])
        self.assertEqual(clauses[0], {"attr": self.champ, "op": "in",
                                      "values": [self.valeurs[0].id]})

    def test_une_COMPARAISON_sur_une_question_numerique_est_gardee(self):
        """Demande de Gerry, 2026-09-07 : les comparaisons valent des deux côtés. ⓘ Ce
        qui distingue `= 7` (« la valeur 7 ») de `= 7` (« sept millimètres ») n'est pas
        l'opérateur, c'est la QUESTION."""
        clause = self._lire([(self.nombre, ">", 4)], numeriques={self.nombre})[0]
        self.assertEqual(clause, {"attr": self.nombre, "op": ">", "value": 4.0})

    def test_une_comparaison_sur_une_question_A_VALEURS_est_refusee(self):
        with self.assertRaises(UserError):
            self._lire([(self.champ, ">", 4)])

    def test_une_question_NUMERIQUE_ne_se_teste_pas_par_appartenance(self):
        with self.assertRaises(UserError):
            self._lire([(self.nombre, "in", [1, 2])], numeriques={self.nombre})

    def test_un_champ_qui_n_est_pas_une_question_est_refuse(self):
        with self.assertRaises(UserError):
            self._lire([("name", "=", "x")])

    def _lire(self, domaine, numeriques=()):
        """Le chemin complet de lecture : les groupes du configurateur, puis nos clauses."""
        groupes = self.env["product.config.domain"]._parse_condition_groups(domaine)
        return domain_to_clauses(domaine, groupes, numeriques)

    # ── CE QUE LA COUTURE PRÉSERVE ───────────────────────────────────────

    def test_une_comparaison_repart_en_feuille_telle_quelle(self):
        presence = {"mode": "condition",
                    "all": [{"attr": self.nombre, "op": ">", "value": 4.0}]}
        self.assertEqual(clauses_to_domain(presence), [(self.nombre, ">", 4.0)])

    def test_vider_la_condition_rend_l_emplacement_TOUJOURS_present(self):
        """Une condition sans clause n'est pas une condition : la contrainte du modèle
        la refuserait, et « toujours » est ce que l'utilisateur vient d'exprimer."""
        self.assertEqual(merge_clauses([]), {"mode": "always"})

    # ── LE CHEMIN COMPLET, PAR L'ASSISTANT ───────────────────────────────

    def test_l_emplacement_ouvre_le_dialogue_du_CONFIGURATEUR(self):
        action = self.lien.action_edit_condition()
        self.assertEqual(action["res_model"], "product.configurator.condition")
        self.assertEqual(action["target"], "new")

    def test_valider_ECRIT_la_condition_sur_le_lien(self):
        action = self.lien.action_edit_condition()
        assistant = self.env["product.configurator.condition"].browse(action["res_id"])
        assistant.condition_domain = str([(self.champ, "in", [self.valeurs[0].id])])
        assistant.action_confirm()
        presence = self.lien.visibility["presence"]
        self.assertEqual(presence["mode"], "condition")
        self.assertEqual(presence["all"][0]["values"], [self.valeurs[0].id])

    def test_le_dialogue_s_ouvre_PRE_REMPLI_de_ce_qui_existe(self):
        self.lien.visibility = {"presence": {
            "mode": "condition",
            "all": [{"attr": self.champ, "op": "in", "values": [self.valeurs[1].id]}]}}
        action = self.lien.action_edit_condition()
        assistant = self.env["product.configurator.condition"].browse(action["res_id"])
        self.assertIn(str(self.valeurs[1].id), assistant.condition_domain)

    def test_une_condition_du_CONFIGURATEUR_ecrit_toujours_dans_son_domaine(self):
        """⚠️ Le crochet ne doit pas détourner l'usage d'origine : sans emplacement,
        l'assistant écrit là où il a toujours écrit."""
        domaine = self.env["product.config.domain"].create({"name": "Test"})
        action = self.env["product.configurator.condition"].open_for(self.produit, domaine)
        assistant = self.env["product.configurator.condition"].browse(action["res_id"])
        self.assertFalse(assistant.component_id)
        assistant.condition_domain = str([(self.champ, "in", [self.valeurs[0].id])])
        assistant.action_confirm()
        self.assertTrue(domaine.domain_line_ids)
