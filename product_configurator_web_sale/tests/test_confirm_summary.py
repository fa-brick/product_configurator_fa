# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La confirmation `lean` : un résumé, pas l'état complet — D-561.

Ce qui est éprouvé : le résumé porte exactement les clés que la page lit avant de partir (variante,
lignes à part, réponses « sans variante », photo, panier), la confirmation complète garde l'état
entier, et la route transmet `lean`.
"""
from odoo import Command
from odoo.tests import HttpCase, tagged

SUMMARY_KEYS = {"state", "productId", "separateLines", "noVariantPtavIds", "photo", "cart", "inCart"}


@tagged("post_install", "-at_install")
class TestConfirmSummary(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        attribute = cls.env["product.attribute"].create({"name": "Couleur D-561", "value_ids": [
            Command.create({"name": "Blanc"}), Command.create({"name": "Noir"})]})
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte D-561", "config_ok": True, "list_price": 100.0,
            "is_published": True, "sale_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": attribute.id, "value_ids": [Command.set(attribute.value_ids.ids)]})],
        })
        cls.white = attribute.value_ids[0]
        cls.website = cls.env.ref("website.default_website")

    def _session(self):
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
            "value_ids": [Command.set(self.white.ids)],
        })
        session._ensure_access_token()
        return session

    def _on_site(self, session):
        return session.with_context(cfg_on_site=True, website_id=self.website.id)

    def test_le_resume_porte_les_seules_cles_lues_avant_de_partir(self):
        session = self._on_site(self._session())
        summary = session.web_confirm(lean=True)
        self.assertEqual(set(summary), SUMMARY_KEYS)
        self.assertEqual(summary["state"], "done")
        self.assertEqual(summary["productId"], session.product_id.id)
        self.assertTrue(summary["cart"])
        self.assertFalse(summary["inCart"])

    def test_sans_lean_la_confirmation_rend_l_etat_complet(self):
        state = self._on_site(self._session()).web_confirm()
        self.assertIn("attributes", state)
        self.assertTrue(SUMMARY_KEYS <= set(state))

    def test_la_route_transmet_lean(self):
        token = self._session().access_token
        summary = self.make_jsonrpc_request("/configurator/confirm", {"token": token, "site": True, "lean": True})
        self.assertEqual(set(summary), SUMMARY_KEYS)
        self.assertNotIn("attributes", summary)
