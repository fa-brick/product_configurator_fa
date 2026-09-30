from odoo import fields, models


class ProductConfigStepLine(models.Model):
    """La vue par DÉFAUT d'une étape — celle qui vaut pour ses attributs muets."""

    _inherit = "product.config.step.line"

    view_camera_id = fields.Many2one(
        comodel_name="product.model3d.camera",
        string="3D View",
        ondelete="set null",
        domain="[('model3d_id.product_tmpl_id', '=', product_tmpl_id)]",
        help="View shown on this step, unless an attribute of the step names "
        "its own.",
    )

    # ⓘ Les crochets du cœur, remplis ici — la colonne « Vue 3D » de l'arbre (D-386).
    def _configurator_camera_name(self):
        self.ensure_one()
        return self.view_camera_id.display_name or ""

    def _configurator_camera_id(self):
        self.ensure_one()
        return self.view_camera_id.id or False

    def _configurator_set_camera(self, camera_id):
        self.ensure_one()
        self.view_camera_id = self.product_tmpl_id._configurator_camera_of(camera_id)
