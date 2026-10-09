# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""DEMANDER UN DEVIS depuis l'environnement (W-111, étape 8.5a, D-426).

Ce qui est éprouvé : le montage devient un devis — une ligne par produit posé, liée à sa
configuration, confirmée ; redemander met à jour le MÊME devis ; une configuration incomplète
bloque et se nomme ; un visiteur se connecte d'abord ; au back-office, le devis est celui du
client ; remplacer ou retirer un produit retire sa ligne ; commandé, le devis libère le chantier
pour un nouveau montage, sur les mêmes baies.
"""
from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.product_configurator_web_3d_environment.tests.test_placement import PlacementCommon


@tagged("post_install", "-at_install")
class TestQuote(PlacementCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()
        cls.customer = cls.env["res.partner"].create({"name": "Client du garage"})
        cls.site.partner_id = cls.customer

    def _lines(self, order):
        return order.order_line.filtered(lambda line: not line.linked_line_id)

    def test_le_montage_devient_un_devis(self):
        self.site.place_product("b1", self.sectional.id)
        placement = self.site.placement_ids
        result = self.site.request_quote()
        order = self.site.order_ids
        self.assertEqual(result["quote"]["name"], order.name)
        self.assertEqual(order.partner_id, self.customer)
        line = self._lines(order)
        self.assertEqual(line.config_session_id, placement.session_id)
        self.assertEqual(placement.session_id.state, "done")
        self.assertEqual(line.product_id, placement.session_id.product_id)
        self.assertEqual((placement.order_id, placement.order_line_id), (order, line))
        self.assertEqual(self.site.editor_state()["quote"]["name"], order.name)

    def test_redemander_met_a_jour_le_meme_devis(self):
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        self.site.request_quote()
        self.assertEqual(len(self.site.order_ids), 1)
        self.assertEqual(len(self._lines(self.site.order_ids)), 1)

    def test_une_configuration_incomplete_bloque_et_se_nomme(self):
        color = self.env["product.attribute"].create({"name": "Couleur sonde", "create_variant": "no_variant"})
        red, blue = self.env["product.attribute.value"].create(
            [{"name": "Rouge sonde", "attribute_id": color.id}, {"name": "Bleu sonde", "attribute_id": color.id}])
        self.sectional.attribute_line_ids = [Command.create(
            {"attribute_id": color.id, "value_ids": [Command.set((red | blue).ids)], "required": True})]
        self.site.place_product("b1", self.sectional.id)
        result = self.site.request_quote()
        self.assertEqual(result["error"], "incomplete")
        self.assertEqual(result["missing"][0]["openingId"], "b1")
        self.assertIn("Couleur sonde", result["missing"][0]["questions"])
        self.assertFalse(self.site.order_ids)

    def test_un_visiteur_se_connecte_d_abord(self):
        self.site.place_product("b1", self.sectional.id)
        public = self.env.ref("base.public_user")
        self.assertEqual(self.site.with_user(public).request_quote(), {"error": "login_required"})

    def test_au_back_office_le_devis_est_celui_du_client(self):
        self.site.partner_id = False
        self.site.place_product("b1", self.sectional.id)
        self.assertEqual(self.site.request_quote()["error"], "no_customer")

    def test_rien_de_pose_rien_a_demander(self):
        self.assertEqual(self.site.request_quote()["error"], "empty")

    def test_remplacer_ou_retirer_retire_la_ligne(self):
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        order = self.site.order_ids
        self.site.place_product("b1", self.simple.id)
        self.assertFalse(self._lines(order))
        self.assertEqual(self.site.placement_ids.order_id, order)  # le montage reste celui du devis
        self.site.request_quote()
        self.assertEqual(self._lines(order).product_id, self.simple.product_variant_id)
        self.site.remove_product("b1")
        self.assertFalse(self._lines(order))

    def test_commande_le_chantier_accueille_un_nouveau_montage(self):
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        order = self.site.order_ids
        order.action_confirm()
        self.assertEqual(self.site.editor_state()["placements"], [])
        self.assertIsNone(self.site.editor_state()["quote"])
        # ⚠️ La même baie reçoit un produit pour un nouveau devis : « une baie, un produit » vaut par montage.
        self.site.place_product("b1", self.sectional.id)
        self.assertEqual(len(self.site.placement_ids), 2)
        self.assertEqual(len(self._lines(order)), 1)


@tagged("post_install", "-at_install")
class TestQuoteRoute(PlacementCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()

    def test_la_route_passe_par_le_jeton_et_demande_une_connexion(self):
        self.site.place_product("b1", self.sectional.id)
        self.assertEqual(self.make_jsonrpc_request("/environment/quote", {"token": "nope"}),
                         {"error": "unknown_environment"})
        self.assertEqual(self.make_jsonrpc_request("/environment/quote", {"token": self.site.access_token}),
                         {"error": "login_required"})
