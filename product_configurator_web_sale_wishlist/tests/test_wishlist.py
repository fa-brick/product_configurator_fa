# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Un produit configuré dans la liste de souhaits — D-557.

Ce qui est éprouvé, sur la page rendue : le nom seul en titre, une réponse par ligne dessous, et
« Configurer » vers une configuration préremplie à la place d'« Ajouter » ; un produit ordinaire
garde la ligne d'Odoo.
"""
from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestWishlist(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        attribute = cls.env["product.attribute"].create({"name": "Couleur D-557", "value_ids": [
            Command.create({"name": "Blanc"}), Command.create({"name": "Noir"})]})
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte D-557", "config_ok": True, "list_price": 100.0,
            "is_published": True, "sale_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": attribute.id, "value_ids": [Command.set(attribute.value_ids.ids)]})],
        })
        # ⚠️ Les attributs neufs sont « Dynamique » : la variante naît de sa combinaison, pas d'avance (D-474).
        black = cls.tmpl.attribute_line_ids.product_template_value_ids.filtered(lambda v: v.name == "Noir")
        cls.variant = cls.tmpl._create_product_variant(black)
        cls.plain = cls.env["product.product"].create({
            "name": "Poignée D-557", "list_price": 10.0, "is_published": True, "sale_ok": True})
        cls.website = cls.env.ref("website.default_website")
        cls.admin = cls.env.ref("base.user_admin")

    def _wishlist_html(self, product):
        self.env["product.wishlist"].create({
            "partner_id": self.admin.partner_id.id, "product_id": product.id,
            "website_id": self.website.id, "price": 100.0,
        })
        self.authenticate("admin", "admin")
        return self.url_open("/shop/wishlist").text

    def test_le_produit_configure_montre_son_nom_puis_ses_reponses(self):
        html = self._wishlist_html(self.variant)
        self.assertIn("Couleur D-557: Noir", html)
        self.assertNotIn("Porte D-557 (Noir)", html)

    def test_configurer_remplace_ajouter_et_part_des_reponses_de_la_variante(self):
        html = self._wishlist_html(self.variant)
        self.assertIn(f"?variant={self.variant.id}", html)
        self.assertIn("o_cfg3d_wish_configure", html)
        self.assertRegex(html, r'id="add_to_cart_button"[^>]*class="[^"]*d-none'
                               r'|class="[^"]*d-none[^"]*"[^>]*id="add_to_cart_button"')

    def test_un_produit_ordinaire_garde_ajouter(self):
        html = self._wishlist_html(self.plain)
        self.assertIn('id="add_to_cart_button"', html)
        self.assertNotRegex(html, r'class="[^"]*d-none[^"]*"[^>]*id="add_to_cart_button"'
                                  r'|id="add_to_cart_button"[^>]*class="[^"]*d-none')
        self.assertNotIn("o_cfg3d_wish_configure", html)
