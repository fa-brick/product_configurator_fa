"""La GRANDE PASTILLE — un type d'affichage de plus (demande de Gerry, 2026-09-29)."""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBigSwatch(TransactionCase):

    def test_le_type_s_enregistre_et_la_page_le_recoit(self):
        attribute = self.env["product.attribute"].create(
            {"name": "Finition bois", "display_type": "swatch"})
        self.assertEqual(attribute.display_type, "swatch")
        # ⓘ La marque du choix : la coche par défaut (le modèle de Gerry).
        self.assertEqual(attribute.swatch_mark, "check")

    def test_la_boutique_le_rend_comme_une_couleur(self):
        """Sans la rustine, `website_sale.variants` n'a pas de cas par défaut : la question
        disparaîtrait de la fiche produit, sans erreur."""
        view = self.env.ref("website_sale.variants", raise_if_not_found=False)
        if not view:
            self.skipTest("boutique absente")
        arch = view._get_combined_arch()
        self.assertTrue(arch.xpath("//t[@t-elif=\"attribute.display_type in ('color', 'swatch')\"]"))


@tagged("post_install", "-at_install")
class TestAnswerSize(TransactionCase):
    """LA TAILLE d'une carte ou d'une grande pastille — D-382 (Gerry, 2026-09-30)."""

    def test_moyenne_par_defaut_l_affichage_d_avant(self):
        attribute = self.env["product.attribute"].create(
            {"name": "Type de plaque", "display_type": "card"})
        self.assertEqual(attribute.answer_size, "medium")

    def test_la_question_de_la_racine_la_recoit(self):
        attribute = self.env["product.attribute"].create(
            {"name": "Type de plaque", "display_type": "card", "answer_size": "small"})
        value = self.env["product.attribute.value"].create(
            {"name": "Carbone", "attribute_id": attribute.id})
        tmpl = self.env["product.template"].create({
            "name": "Plaque configurable", "config_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": attribute.id, "value_ids": [Command.set(value.ids)],
            })],
        })
        session = self.env["product.config.session"].create(
            {"product_tmpl_id": tmpl.id, "user_id": self.env.user.id})
        question = session.web_state()["attributes"][0]
        self.assertEqual(question["answerSize"], "small")
