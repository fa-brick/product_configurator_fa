# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La VUE 3D choisie dans l'arbre du configurateur — D-386.

Gerry (2026-09-30) : *« on voit une colonne 3D view mais pas de liste déroulante pour
choisir »*. Le cœur ne connaît pas les caméras (D-075) : il demande les choix au pont et
lui délègue l'écriture — pour un attribut comme pour une étape.
"""
from odoo import Command
from odoo.exceptions import UserError

from odoo.addons.base.tests.common import BaseCommon


class TreeCamera(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lock = cls.env["product.attribute"].create(
            {"name": "Lock", "create_variant": "no_variant"})
        value = cls.env["product.attribute.value"].create(
            {"name": "With lock", "attribute_id": cls.lock.id})
        cls.template = cls.env["product.template"].create({
            "name": "Door with views", "config_ok": True,
            "attribute_line_ids": [Command.create(
                {"attribute_id": cls.lock.id, "value_ids": [Command.set(value.ids)]})],
        })
        cls.line = cls.template.attribute_line_ids
        cls.step = cls.env["product.config.step"].create({"name": "Hardware"})
        cls.line.config_step_id = cls.step
        model3d = cls.env["product.model3d"].create(
            {"name": "Panel", "product_tmpl_id": cls.template.id})
        cls.front, cls.close_up = cls.env["product.model3d.camera"].create([
            {"name": "Front", "model3d_id": model3d.id},
            {"name": "Lock close-up", "model3d_id": model3d.id},
        ])
        other = cls.env["product.template"].create({"name": "Other", "config_ok": True})
        cls.foreign = cls.env["product.model3d.camera"].create({
            "name": "Elsewhere",
            "model3d_id": cls.env["product.model3d"].create(
                {"name": "Other", "product_tmpl_id": other.id}).id,
        })

    def _row(self, kind):
        return next(r for r in self.template.get_configurator_tree() if r["kind"] == kind)

    def test_01_the_list_offers_the_views_of_THIS_product(self):
        names = [c["name"] for c in self.template.configurator_camera_choices()]
        self.assertEqual(names, ["Front", "Lock close-up"])

    def test_02_an_attribute_view_is_chosen_from_the_tree(self):
        self.template.configurator_set_camera("attribute", self.line.id, self.close_up.id)
        self.assertEqual(self.line.view_camera_id, self.close_up)
        self.assertEqual(self._row("attribute")["camera_id"], self.close_up.id)

    def test_03_and_a_STEP_view_too_on_its_step_line(self):
        """⚠️ Sur la ligne d'étape DU PRODUIT, jamais sur `product.config.step`, partagé."""
        self.template.configurator_set_camera("step", self.step.id, self.front.id)
        step_line = self.template.config_step_line_ids
        self.assertEqual(step_line.view_camera_id, self.front)
        self.assertEqual(self._row("step")["camera_id"], self.front.id)
        self.assertEqual(self._row("step")["camera"], "Front")

    def test_04_an_empty_choice_clears_the_view(self):
        self.line.view_camera_id = self.front
        self.template.configurator_set_camera("attribute", self.line.id, False)
        self.assertFalse(self.line.view_camera_id)

    def test_05_a_view_of_ANOTHER_product_is_refused(self):
        with self.assertRaises(UserError):
            self.template.configurator_set_camera("attribute", self.line.id, self.foreign.id)
        self.assertFalse(self.line.view_camera_id)

    def test_06_a_line_of_ANOTHER_product_is_refused(self):
        other_line = self.env["product.template.attribute.line"].search(
            [("product_tmpl_id", "!=", self.template.id)], limit=1)
        if not other_line:
            self.skipTest("no other attribute line in this database")
        with self.assertRaises(UserError):
            self.template.configurator_set_camera("attribute", other_line.id, self.front.id)
