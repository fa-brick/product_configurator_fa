# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""DEMANDER UN DEVIS depuis l'environnement (W-111, étape 8.5a, D-426).

Ce qui est éprouvé : le montage devient un devis — une ligne par produit posé, liée à sa
configuration, confirmée ; redemander met à jour le MÊME devis ; une configuration incomplète
bloque et se nomme ; un visiteur se connecte d'abord ; au back-office, le devis est celui du
client ; remplacer ou retirer un produit retire sa ligne ; commandé, le devis libère le chantier
pour un nouveau montage, sur les mêmes baies ; le jeton d'un devis ouvre SON montage, en lecture
seule une fois commandé (8.5b) ; modifier les murs d'un montage que d'autres devis lisent en fait une
copie propre au devis, et un plan refusé n'en laisse aucune (8.5c).
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


    def test_chaque_devis_montre_son_montage(self):
        # Devis A commandé, puis un nouveau montage sur la même baie : chaque devis montre le sien.
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        first = self.site.order_ids
        first.action_confirm()
        self.site.place_product("b1", self.simple.id)
        self.site.request_quote()
        second = self.site.order_ids - first
        in_first = self.site.with_context(environment_order_id=first.id)
        self.assertEqual([p["productId"] for p in in_first.editor_state()["placements"]], [self.sectional.id])
        self.assertFalse(in_first.editor_state()["can_write"])  # commandé : lecture seule
        in_second = self.site.with_context(environment_order_id=second.id)
        self.assertEqual([p["productId"] for p in in_second.editor_state()["placements"]], [self.simple.id])
        self.assertTrue(in_second.editor_state()["can_write"])

    def test_le_bouton_montage_ouvre_l_editeur_par_le_jeton_du_devis(self):
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        order = self.site.order_ids
        action = order.action_open_montage()
        self.assertEqual(action["tag"], "product_editor_environment.editor")
        self.assertEqual(action["params"]["token"], order.access_token)
        self.assertEqual(action["params"]["state"]["quote"]["name"], order.name)


    def _wider_bay(self, environment, width=2600):
        plan = dict(environment.plan)
        plan["openings"] = [dict(opening, width=width) for opening in plan["openings"]]
        return plan

    def test_modifier_les_murs_depuis_un_devis_en_fait_une_copie(self):
        # Devis A commandé, devis B en cours sur le même chantier : B modifie la baie.
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        first = self.site.order_ids
        first.action_confirm()
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        second = self.site.order_ids - first
        in_second = self.site.with_context(environment_order_id=second.id)
        result = in_second.editor_save(self._wider_bay(self.site))
        self.assertTrue(result["copied"])
        self.assertEqual(result["token"], second.access_token)
        copy = second.environment_id
        self.assertNotEqual(copy, self.site)
        self.assertEqual(first.environment_id, self.site)
        self.assertEqual(self.site.plan["openings"][0]["width"], 2400)   # A garde son plan
        self.assertEqual(copy.plan["openings"][0]["width"], 2600)
        self.assertEqual(second.environment_placement_ids.environment_id, copy)
        self.assertEqual(first.environment_placement_ids.environment_id, self.site)
        # Le produit de B a suivi sa baie dans la copie (D-424).
        answers = {c.attribute_id: c.value for c in second.environment_placement_ids.session_id.custom_value_ids}
        self.assertEqual(answers[self.width], "2600")

    def test_seul_lecteur_pas_de_copie(self):
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        result = self.site.editor_save(self._wider_bay(self.site))
        self.assertTrue(result["ok"])
        self.assertFalse(result.get("copied"))
        self.assertEqual(self.site.order_ids.environment_id, self.site)

    def test_un_plan_refuse_ne_laisse_pas_de_copie(self):
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        first = self.site.order_ids
        first.action_confirm()
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        second = self.site.order_ids - first
        sites = self.env["product.environment"].search_count([])
        plan = self._wider_bay(self.site, width=9000)   # dépasse le mur
        result = self.site.with_context(environment_order_id=second.id).editor_save(plan)
        self.assertEqual(result["error"], "invalid")
        self.assertEqual(self.env["product.environment"].search_count([]), sites)
        self.assertEqual(second.environment_id, self.site)


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

    def test_le_jeton_du_devis_ouvre_son_montage(self):
        self.site.partner_id = self.env["res.partner"].create({"name": "Client route"})
        self.site.place_product("b1", self.sectional.id)
        self.site.request_quote()
        order = self.site.order_ids
        state = self.make_jsonrpc_request("/environment/state", {"token": order.access_token})
        self.assertEqual(state["quote"]["name"], order.name)
        self.assertEqual([p["openingId"] for p in state["placements"]], ["b1"])
        # Le devis commandé : son montage se lit, ne s'écrit plus.
        order.action_confirm()
        state = self.make_jsonrpc_request("/environment/state", {"token": order.access_token})
        self.assertFalse(state["can_write"])
        self.assertEqual(self.make_jsonrpc_request("/environment/unplace", {"token": order.access_token, "opening_id": "b1"}),
                         {"error": "read_only"})
