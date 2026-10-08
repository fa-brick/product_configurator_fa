# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""POSER un produit dans une baie (W-111, étape 8.4c).

Ce qui est éprouvé : la pose d'un produit configurable crée sa configuration avec la largeur et la
hauteur de la baie (U-2) ; un produit qui ne se configure pas se pose tel quel ; un produit que la
baie ne propose pas est refusé ; reposer REMPLACE ; l'éditeur sait poser et lit ce qui est posé ;
la route passe par le jeton.
"""
from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged


def garage_plan(accepts):
    nodes = [{"id": "n1", "x": 0, "y": 0}, {"id": "n2", "x": 3000, "y": 0},
             {"id": "n3", "x": 3000, "y": 6000}, {"id": "n4", "x": 0, "y": 6000}]
    walls = [{"id": "w%d" % i, "a": "n%d" % i, "b": "n%d" % (i % 4 + 1)} for i in range(1, 5)]
    return {"version": 1, "nodes": nodes, "walls": walls, "openings": [
        {"id": "b1", "wall": "w1", "kind": "bay", "offset": 300, "width": 2400, "height": 2100,
         "sill": 0, "accepts": accepts}]}


class PlacementCommon:

    @classmethod
    def _fixture(cls):
        env = cls.env
        Attribute, Value = env["product.attribute"], env["product.attribute.value"]
        mm = env.ref("uom.product_uom_millimeter")
        cls.width = Attribute.create({"name": "Largeur commune", "val_custom": True, "custom_type": "float",
                                      "uom_id": mm.id, "create_variant": "no_variant"})
        cls.height = Attribute.create({"name": "Hauteur commune", "val_custom": True, "custom_type": "float",
                                       "uom_id": mm.id, "create_variant": "no_variant"})
        params = env["ir.config_parameter"].sudo()
        params.set_param("product_editor_environment.width_attribute_id", cls.width.id)
        params.set_param("product_editor_environment.height_attribute_id", cls.height.id)
        cls.doors = env["product.category"].create({"name": "Portes de garage pose"})

        values = {}

        def line(attribute, low, high):
            # ⓘ Une valeur par (attribut, nom) : Odoo refuse les doublons.
            value = values.get((attribute, low)) or Value.create({"name": str(low), "attribute_id": attribute.id})
            values[(attribute, low)] = value
            return Command.create({"attribute_id": attribute.id, "value_ids": [Command.set(value.ids)],
                                   "custom": True, "required": True,
                                   "has_min_val": True, "min_val": low, "has_max_val": True, "max_val": high})

        cls.sectional = env["product.template"].create({
            "name": "Sectionnelle à poser", "config_ok": True, "categ_id": cls.doors.id,
            "attribute_line_ids": [line(cls.width, 2000, 3000), line(cls.height, 1800, 2400)]})
        cls.simple = env["product.template"].create({
            "name": "Porte simple à poser", "categ_id": cls.doors.id,
            "attribute_line_ids": [line(cls.width, 2000, 3000), line(cls.height, 1800, 2400)]})
        cls.narrow = env["product.template"].create({
            "name": "Porte étroite à poser", "config_ok": True, "categ_id": cls.doors.id,
            "attribute_line_ids": [line(cls.width, 1000, 2000), line(cls.height, 1800, 2400)]})
        cls.site = env["product.environment"].create({"name": "Garage", "plan": garage_plan(cls.doors.id)})


@tagged("post_install", "-at_install")
class TestPlacement(PlacementCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()

    def test_l_editeur_sait_poser(self):
        state = self.site.editor_state()
        self.assertTrue(state["can_place"])
        self.assertEqual(state["placements"], [])

    def test_la_configuration_nait_avec_les_mesures_de_la_baie(self):
        result = self.site.place_product("b1", self.sectional.id)
        placement = self.site.placement_ids
        self.assertEqual(result["placement"]["productName"], "Sectionnelle à poser")
        self.assertTrue(result["placement"]["token"])
        answers = {c.attribute_id: c.value for c in placement.session_id.custom_value_ids}
        self.assertEqual(answers[self.width], "2400")
        self.assertEqual(answers[self.height], "2100")

    def test_un_produit_non_configurable_se_pose_tel_quel(self):
        result = self.site.place_product("b1", self.simple.id)
        self.assertFalse(self.site.placement_ids.session_id)
        self.assertIsNone(result["placement"]["token"])

    def test_un_produit_que_la_baie_ne_propose_pas_est_refuse(self):
        self.assertEqual(self.site.place_product("b1", self.narrow.id)["error"], "not_offered")
        self.assertEqual(self.site.place_product("nope", self.sectional.id)["error"], "not_offered")
        self.assertFalse(self.site.placement_ids)

    def test_reposer_remplace(self):
        self.site.place_product("b1", self.sectional.id)
        self.site.place_product("b1", self.simple.id)
        self.assertEqual(self.site.placement_ids.product_tmpl_id, self.simple)
        self.assertEqual([p["productId"] for p in self.site.editor_state()["placements"]], [self.simple.id])


@tagged("post_install", "-at_install")
class TestPlacementRoute(PlacementCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()

    def test_la_route_pose_par_le_jeton(self):
        result = self.make_jsonrpc_request("/environment/place", {
            "token": self.site.access_token, "opening_id": "b1", "product_tmpl_id": self.sectional.id})
        self.assertEqual(result["placement"]["openingId"], "b1")
        self.assertEqual(self.make_jsonrpc_request("/environment/place", {
            "token": "nope", "opening_id": "b1", "product_tmpl_id": self.sectional.id}),
            {"error": "unknown_environment"})
