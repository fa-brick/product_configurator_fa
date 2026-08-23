"""La VUE que le configurateur affiche — D-163.

Une règle, trois cas, et le troisième est le plus important : quand rien n'est
déclaré, la caméra **ne bouge pas**. Le client garde le cadrage qu'il s'est
donné (arbitrage Gerry, précédent D-125).
"""

from odoo.addons.base.tests.common import BaseCommon


class ViewResolution(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = cls.env["product.template"].create(
            {"name": "Door with views", "config_ok": True}
        )
        cls.model3d = cls.env["product.model3d"].create(
            {"name": "Panel", "product_tmpl_id": cls.template.id}
        )
        cls.view_front = cls.env["product.model3d.camera"].create(
            {"name": "Front", "model3d_id": cls.model3d.id}
        )
        cls.view_lock = cls.env["product.model3d.camera"].create(
            {"name": "Lock close-up", "model3d_id": cls.model3d.id}
        )
        cls.attribute = cls.env["product.attribute"].create(
            {"name": "Lock", "create_variant": "no_variant"}
        )
        cls.value = cls.env["product.attribute.value"].create(
            {"name": "With lock", "attribute_id": cls.attribute.id}
        )
        cls.line = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attribute.id,
                "value_ids": [(6, 0, [cls.value.id])],
            }
        )
        step = cls.env["product.config.step"].create({"name": "Hardware"})
        cls.step_line = cls.env["product.config.step.line"].create(
            {
                "config_step_id": step.id,
                "product_tmpl_id": cls.template.id,
                "attribute_line_ids": [(6, 0, [cls.line.id])],
            }
        )

    def test_01_the_attribute_view_wins(self):
        self.line.view_camera_id = self.view_lock
        self.step_line.view_camera_id = self.view_front
        self.assertEqual(self.line._resolve_view_camera(self.step_line), self.view_lock)

    def test_02_the_step_view_applies_by_default(self):
        self.step_line.view_camera_id = self.view_front
        self.assertEqual(self.line._resolve_view_camera(self.step_line), self.view_front)

    def test_03_without_a_view_the_camera_does_not_move(self):
        """⚠️ Rien ne veut PAS dire « la vue par défaut » : revenir au défaut
        annulerait le cadrage du client à chaque étape muette."""
        self.assertFalse(self.line._resolve_view_camera(self.step_line))
        self.assertFalse(self.line._resolve_view_camera())
