# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Au panier, une ligne configurée : le nom en titre, les réponses dessous — D-555.

Le panier d'Odoo écrit `name_short` en titre et `get_description_following_lines()` dessous.
"""
from odoo import Command

from odoo.addons.website_sale.tests.common import WebsiteSaleCommon


class CartLineTitle(WebsiteSaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plate = cls.env["product.attribute"].create({"name": "Plaque", "value_ids": [
            Command.create({"name": "Classic"}), Command.create({"name": "Light"})]})
        cls.tmpl = cls.env["product.template"].create({
            "name": "Drone D-555", "config_ok": True, "list_price": 100.0,
            "is_published": True, "sale_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.plate.id, "value_ids": [Command.set(cls.plate.value_ids.ids)]})],
        })

    def _cart_line(self):
        # ⚠️ Les attributs neufs sont « Dynamique » : la variante naît de sa combinaison, pas d'avance (D-474).
        light = self.tmpl.attribute_line_ids.product_template_value_ids.filtered(
            lambda ptav: ptav.name == "Light")
        product = self.tmpl._create_product_variant(light)
        # ⓘ La référence interne d'une variante née après le modèle se pose sur elle.
        product.default_code = "DR555"
        result = self.empty_cart._cart_update(product_id=product.id, add_qty=1)
        return self.empty_cart.order_line.browse(result["line_id"])

    def test_le_titre_est_le_nom_sans_reference_et_les_reponses_viennent_dessous(self):
        line = self._cart_line()
        self.assertEqual(line.name_short, "Drone D-555")
        self.assertEqual(line.get_description_following_lines(), ["Plaque: Light"])

    def test_une_ligne_ecrite_avant_garde_son_titre(self):
        line = self._cart_line()
        line.name = "[DR555] Drone D-555 (Light)"
        self.assertEqual(line.name_short, "Drone D-555 (Light)")

    def test_un_article_ordinaire_garde_le_titre_d_odoo(self):
        self.tmpl.config_ok = False
        line = self._cart_line()
        self.assertEqual(line.name_short, "Drone D-555 (Light)")
