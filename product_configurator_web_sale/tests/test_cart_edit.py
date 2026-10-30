# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Modifier une configuration depuis le panier — D-556.

Ce qui est éprouvé : le lien de la ligne (présent tant que le panier est un brouillon, absent
sans configuration), le drapeau `inCart` de l'état, qui fait revenir la page au panier et
l'empêche d'y ajouter une seconde ligne, et le lien rendu dans `/shop/cart`.
"""
from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestCartEdit(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        attribute = cls.env["product.attribute"].create({"name": "Couleur D-556", "value_ids": [
            Command.create({"name": "Blanc"}), Command.create({"name": "Noir"})]})
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte D-556", "config_ok": True, "list_price": 100.0,
            "is_published": True, "sale_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": attribute.id, "value_ids": [Command.set(attribute.value_ids.ids)]})],
        })
        cls.white = attribute.value_ids[0]
        cls.website = cls.env.ref("website.default_website")
        cls.admin = cls.env.ref("base.user_admin")

    def _configured_order(self, website=True):
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.admin.id,
            "value_ids": [Command.set(self.white.ids)],
        })
        session.action_confirm()
        session._ensure_access_token()
        order = self.env["sale.order"].create({
            "partner_id": self.admin.partner_id.id,
            "website_id": self.website.id if website else False,
            "order_line": [Command.create({"product_id": session.product_id.id,
                                           "config_session_id": session.id})],
        })
        return session, order

    def _on_site(self, session):
        return session.with_context(cfg_on_site=True, website_id=self.website.id)

    def test_la_ligne_configuree_d_un_panier_porte_le_lien_de_sa_configuration(self):
        session, order = self._configured_order()
        self.assertEqual(order.order_line._configurator_edit_url(),
                         f"/configurator/{session.access_token}")

    def test_une_commande_confirmee_n_offre_plus_de_lien(self):
        _session, order = self._configured_order()
        order.action_confirm()
        self.assertFalse(order.order_line._configurator_edit_url())

    def test_une_ligne_sans_configuration_n_a_pas_de_lien(self):
        order = self.env["sale.order"].create({
            "partner_id": self.admin.partner_id.id, "website_id": self.website.id,
            "order_line": [Command.create({"product_id": self.env["product.product"].create(
                {"name": "Poignée D-556"}).id})],
        })
        self.assertFalse(order.order_line._configurator_edit_url())

    def test_une_configuration_du_panier_le_dit_et_n_y_retourne_pas_une_seconde_fois(self):
        session, _order = self._configured_order()
        state = self._on_site(session).web_state()
        self.assertTrue(state["inCart"])
        self.assertFalse(state["cart"])

    def test_un_devis_du_back_office_n_est_pas_un_panier(self):
        session, _order = self._configured_order(website=False)
        self.assertFalse(self._on_site(session).web_state()["inCart"])

    def test_le_panier_affiche_le_lien_modifier(self):
        # ⓘ Le panier de l'admin connecté est son dernier brouillon du site : celui-ci, le plus récent.
        session, _order = self._configured_order()
        self.authenticate("admin", "admin")
        html = self.url_open("/shop/cart").text
        self.assertIn(f'href="/configurator/{session.access_token}"', html)
        self.assertIn("o_cfg3d_cart_edit", html)
