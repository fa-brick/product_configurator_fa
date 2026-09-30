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


@tagged("post_install", "-at_install")
class TestAnswerLayout(TransactionCase):
    """LA DISPOSITION des réponses — D-382 (Gerry, 2026-09-30)."""

    def _attribute(self, display_type, layout):
        vals = {"name": "Q", "display_type": display_type, "answer_layout": layout}
        # ⓘ Des cases à cocher n'engendrent pas de variante : contrainte du cœur d'Odoo.
        if display_type == "multi":
            vals["create_variant"] = "no_variant"
        return self.env["product.attribute"].create(vals)

    def test_liste_complete_par_defaut_l_affichage_d_avant(self):
        attribute = self.env["product.attribute"].create({"name": "Q", "display_type": "card"})
        self.assertEqual(attribute.answer_layout, "inline")
        self.assertEqual(attribute._web_answer_layout(), "inline")

    def test_defilement_et_ligne_pour_les_formes_a_image_seulement(self):
        for layout in ("scroll", "line"):
            for form in ("card", "swatch"):
                self.assertEqual(self._attribute(form, layout)._web_answer_layout(), layout)
            for form in ("radio", "pills", "select", "color", "multi"):
                self.assertEqual(self._attribute(form, layout)._web_answer_layout(), "inline",
                                 "%s / %s" % (form, layout))

    def test_le_resume_aussi_pour_les_boutons_et_la_liste(self):
        for form in ("card", "swatch", "radio", "pills", "select"):
            self.assertEqual(self._attribute(form, "summary")._web_answer_layout(), "summary")
        for form in ("color", "multi"):
            self.assertEqual(self._attribute(form, "summary")._web_answer_layout(), "inline")

    def test_changer_la_forme_apres_coup_ne_leve_rien(self):
        """Pas de contrainte : elle interdirait de changer la forme d'un attribut réglé."""
        attribute = self._attribute("card", "scroll")
        attribute.display_type = "radio"
        self.assertEqual(attribute.answer_layout, "scroll")
        self.assertEqual(attribute._web_answer_layout(), "inline")
