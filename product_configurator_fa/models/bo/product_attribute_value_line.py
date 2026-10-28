"""Ce que déclare `product.attribute.value.line` (BO, D-541)."""
from odoo import fields, models


class ProductAttributeValueLine(models.Model):
    _name = "product.attribute.value.line"
    _description = "Product Attribute Value Line"
    _order = "sequence"

    sequence = fields.Integer(default=10)

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product Template",
        ondelete="cascade",
        required=True,
    )

    value_id = fields.Many2one(
        comodel_name="product.attribute.value",
        required=True,
        string="Attribute Value",
    )

    attribute_id = fields.Many2one(
        comodel_name="product.attribute", related="value_id.attribute_id"
    )

    value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        relation="product_attribute_value_product_attribute_value_line_rel",
        column1="product_attribute_value_line_id",
        column2="product_attribute_value_id",
        string="Values Configuration",
    )
