# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Une cote hors de la grille de prix : la page le dit, la confirmation est refusée — D-537."""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOutOfGrid(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mm = cls.env.ref("uom.product_uom_millimeter")
        cls.width, cls.height = cls.env["product.attribute"].create([
            {"name": name, "val_custom": True, "custom_type": "float", "uom_id": mm.id,
             "create_variant": "dynamic"}
            for name in ("Largeur", "Hauteur")
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Portail", "config_ok": True, "list_price": 100,
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.width.id, "custom": True,
                                "required": False, "dimension_role": "axis_x"}),
                Command.create({"attribute_id": cls.height.id, "custom": True,
                                "required": False, "dimension_role": "axis_y"}),
            ],
        })
        grid = cls.env["product.price.grid"].create(
            {"name": "Tarif", "product_tmpl_id": cls.tmpl.id})
        x, y = cls.env["product.price.grid.bracket"].create([
            {"grid_id": grid.id, "axis": "x", "max_value": 3000},
            {"grid_id": grid.id, "axis": "y", "max_value": 2400},
        ])
        cls.env["product.price.grid.cell"].create(
            {"grid_id": grid.id, "x_bracket_id": x.id, "y_bracket_id": y.id, "price": 500})

    def _session(self, width, height):
        session = self.env["product.config.session"].create_get_session(
            self.tmpl.id, force_create=True)
        for attribute, value in ((self.width, width), (self.height, height)):
            self.env["product.config.session.custom.value"].create(
                {"attribute_id": attribute.id, "cfg_session_id": session.id, "value": value})
        return session

    def test_la_page_recoit_le_message_avec_la_borne_depassee(self):
        message = self._session(3500, 2000).web_state()["outOfGrid"]
        self.assertIn("Largeur", message)
        self.assertIn("3000", message)
        self.assertNotIn("Hauteur", message)

    def test_une_cote_dans_la_grille_n_a_pas_de_message(self):
        self.assertFalse(self._session(2000, 2000).web_state()["outOfGrid"])

    def test_la_confirmation_est_refusee_hors_grille(self):
        session = self._session(3500, 2000)
        result = session.web_confirm()
        self.assertEqual(result.get("error"), "out_of_grid")
        self.assertEqual(session.state, "draft")
