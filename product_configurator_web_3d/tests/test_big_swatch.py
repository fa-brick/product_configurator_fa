"""La GRANDE PASTILLE — un type d'affichage de plus (demande de Gerry, 2026-09-29)."""
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
