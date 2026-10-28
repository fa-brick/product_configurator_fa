"""Ce que déclare `product.config.image` (BO, D-541)."""
from odoo import fields, models


class ProductConfigImage(models.Model):
    _name = "product.config.image"
    _description = "Product Config Image"
    _inherit = ["image.mixin"]
    _order = "sequence"

    name = fields.Char(required=True, translate=True)

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product",
        ondelete="cascade",
        required=True,
    )

    sequence = fields.Integer(default=10)

    value_ids = fields.Many2many(
        comodel_name="product.attribute.value", string="Configuration"
    )
