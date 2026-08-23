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
