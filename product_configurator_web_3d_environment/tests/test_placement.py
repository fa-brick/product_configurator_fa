# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""POSER un produit dans une baie (W-111, étape 8.4c).

Ce qui est éprouvé : la pose d'un produit configurable crée sa configuration avec la largeur et la
hauteur de la baie (U-2) ; un produit qui ne se configure pas se pose tel quel ; un produit que la
baie ne propose pas est refusé ; reposer REMPLACE ; l'éditeur sait poser et lit ce qui est posé ;
la route passe par le jeton ; le produit suit sa baie en gardant l'écart du client (8.4e, D-424).
"""
from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged


def garage_plan():
    nodes = [{"id": "n1", "x": 0, "y": 0}, {"id": "n2", "x": 3000, "y": 0},
             {"id": "n3", "x": 3000, "y": 6000}, {"id": "n4", "x": 0, "y": 6000}]
    walls = [{"id": "w%d" % i, "a": "n%d" % i, "b": "n%d" % (i % 4 + 1)} for i in range(1, 5)]
    return {"version": 1, "nodes": nodes, "walls": walls, "openings": [
        {"id": "b1", "wall": "w1", "offset": 300, "width": 2400, "height": 2100, "sill": 0}]}


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
        cls.site = env["product.environment"].create({"name": "Garage", "plan": garage_plan()})


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

    def test_retirer_libere_la_baie_et_garde_la_configuration(self):
        self.site.place_product("b1", self.sectional.id)
        session = self.site.placement_ids.session_id
        self.assertEqual(self.site.remove_product("b1"), {"ok": True})
        self.assertFalse(self.site.placement_ids)
        self.assertTrue(session.exists())
        self.assertEqual(self.site.remove_product("b1"), {"error": "not_placed"})

    def test_reposer_remplace(self):
        self.site.place_product("b1", self.sectional.id)
        self.site.place_product("b1", self.simple.id)
        self.assertEqual(self.site.placement_ids.product_tmpl_id, self.simple)
        self.assertEqual([p["productId"] for p in self.site.editor_state()["placements"]], [self.simple.id])


@tagged("post_install", "-at_install")
class TestPlacementFollowsBay(PlacementCommon, TransactionCase):
    """Le produit SUIT sa baie, en gardant l'écart que le client y a mis (D-424, comme D-047)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()

    def setUp(self):
        super().setUp()
        self.site.place_product("b1", self.sectional.id)
        self.session = self.site.placement_ids.session_id

    def _resize_bay(self, **dims):
        plan = dict(self.site.plan)
        plan["openings"] = [dict(opening, **dims) for opening in plan["openings"]]
        return self.site.editor_save(plan)

    def _answers(self):
        return {c.attribute_id: c.value for c in self.session.custom_value_ids}

    def test_le_produit_suit_sa_baie(self):
        result = self._resize_bay(width=2600)
        self.assertEqual(result["followed"], [self.session.access_token])
        self.assertEqual(result["messages"], [])
        self.assertEqual(self._answers()[self.width], "2600")
        self.assertEqual(self._answers()[self.height], "2100")

    def test_l_ecart_du_client_se_garde(self):
        self.session.web_set_custom_value(self.width.id, "2300")
        self.assertEqual(self.site.editor_state()["placements"][0]["offsets"], {"width": -100.0, "height": 0.0})
        self._resize_bay(width=2600)
        self.assertEqual(self._answers()[self.width], "2500")

    def test_une_valeur_offerte_suit_aussi(self):
        # « 2000 » est une valeur OFFERTE : la réponse est un choix, pas une saisie.
        self.session.web_set_custom_value(self.width.id, "2000")
        self.assertNotIn(self.width, self._answers())
        self._resize_bay(width=2600)
        self.assertEqual(self._answers()[self.width], "2200")

    def test_un_refus_se_dit_et_la_baie_est_enregistree(self):
        # 2 450 dépasse la hauteur maximale du produit (2 400) : la baie fait foi, le produit garde sa réponse.
        result = self._resize_bay(height=2450)
        self.assertTrue(result["ok"])
        self.assertEqual(result["followed"], [])
        self.assertEqual(len(result["messages"]), 1)
        self.assertEqual(self._answers()[self.height], "2100")
        self.assertEqual(self.site.plan["openings"][0]["height"], 2450)

    def test_un_plan_qui_retire_une_baie_equipee_est_refuse(self):
        """§14.5 : la forme d'un autre modèle ne reprend pas le produit d'une baie qu'elle efface."""
        before = self.site.plan
        plan = dict(before, openings=[])
        result = self.site.editor_save(plan)
        self.assertEqual(result["error"], "invalid")
        self.assertIn("Sectionnelle à poser", result["messages"][0])
        self.assertEqual(self.site.plan, before)
        # Le produit retiré, la baie peut partir.
        self.site.remove_product("b1")
        self.assertTrue(self.site.editor_save(plan)["ok"])

    def test_une_baie_inchangee_ne_touche_a_rien(self):
        self.session.web_set_custom_value(self.width.id, "2300")
        self.assertEqual(self._resize_bay(sill=0)["followed"], [])
        self.assertEqual(self._answers()[self.width], "2300")


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

    def test_la_route_retire_par_le_jeton(self):
        self.site.place_product("b1", self.sectional.id)
        self.assertEqual(self.make_jsonrpc_request("/environment/unplace", {"token": "nope", "opening_id": "b1"}),
                         {"error": "unknown_environment"})
        self.assertEqual(self.make_jsonrpc_request("/environment/unplace", {
            "token": self.site.access_token, "opening_id": "b1"}), {"ok": True})
        self.assertFalse(self.site.placement_ids)


@tagged("post_install", "-at_install")
class TestPlacementShape(PlacementCommon, TransactionCase):
    """La FORME d'un produit posé dans un trou existant (W-113, E-3d-4b, Q-30.4, Q-30.5) : la valeur du type du trou."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()
        Type = cls.env["product.environment.opening.type"]
        cls.straight_type = Type.create({"name": "Fenêtre droite pose", "width": 2400, "height": 2100})
        cls.arched_type = Type.create({"name": "Fenêtre cintrée pose", "shape": "segmental_arch", "width": 2400,
                                       "height": 2100, "rise": 300})
        cls.oculus_type = Type.create({"name": "Œil-de-bœuf pose", "shape": "ellipse", "width": 2400, "height": 2100})
        shape = cls.env["product.attribute"].create({"name": "Forme pose", "create_variant": "no_variant"})
        Value = cls.env["product.attribute.value"]
        cls.straight = Value.create({"name": "Droite", "attribute_id": shape.id,
                                     "environment_opening_type_id": cls.straight_type.id})
        cls.arched = Value.create({"name": "Cintrée", "attribute_id": shape.id,
                                   "environment_opening_type_id": cls.arched_type.id})
        cls.sectional.write({
            "environment_opening_type_ids": [Command.set((cls.straight_type | cls.arched_type | cls.oculus_type).ids)],
            "attribute_line_ids": [Command.create({"attribute_id": shape.id,
                                                   "value_ids": [Command.set((cls.straight | cls.arched).ids)]})]})

    def _hole(self, opening_type):
        plan = garage_plan()
        plan["openings"][0]["type"] = opening_type.id
        self.site.plan = plan

    def test_la_forme_suit_le_type_du_trou(self):
        for opening_type, value in ((self.straight_type, self.straight), (self.arched_type, self.arched)):
            self._hole(opening_type)
            self.site.place_product("b1", self.sectional.id)
            chosen = self.site.placement_ids.session_id.value_ids
            self.assertIn(value, chosen)
            self.assertNotIn((self.straight | self.arched) - value, chosen)

    def test_un_trou_sans_valeur_de_forme_ne_propose_pas_le_produit(self):
        # ⚠️ Lié au type « Œil-de-bœuf », mais sans valeur de forme pour lui : pas proposé (Q-30.5).
        self._hole(self.oculus_type)
        self.assertNotIn(self.sectional.id, [p["id"] for p in self.site.bay_products("b1")["products"]])
        self.assertEqual(self.site.place_product("b1", self.sectional.id)["error"], "not_offered")
