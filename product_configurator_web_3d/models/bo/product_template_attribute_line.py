"""Ce que déclare `product.template.attribute.line` (BO, D-541)."""
from odoo import fields, models


class ProductAttributeLine(models.Model):
    """La VUE 3D que le configurateur affiche pour cet attribut — D-163.

    ⚠️ Ne pas le poser dans le cœur du configurateur : il pointe une caméra de
    `product_editor`, et le cœur en dépendrait (D-163).
    """
    _inherit = "product.template.attribute.line"

    view_camera_id = fields.Many2one(
        comodel_name="product.model3d.camera",
        string="3D View",
        ondelete="set null",
        domain="[('model3d_id.product_tmpl_id', '=', product_tmpl_id)]",
        help="View shown while this attribute is being answered. Empty means "
        "the camera does not move.",
    )
