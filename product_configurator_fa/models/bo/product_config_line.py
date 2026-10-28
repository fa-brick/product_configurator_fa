"""Ce que déclare `product.config.line` (BO, D-541)."""
from odoo import fields, models


class ProductConfigLine(models.Model):
    _name = "product.config.line"
    _description = "Product Config Restrictions"
    _order = "product_tmpl_id, sequence, id"

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product Template",
        ondelete="cascade",
        required=True,
    )

    attribute_line_id = fields.Many2one(
        comodel_name="product.template.attribute.line",
        string="Attribute Line",
        ondelete="cascade",
        required=True,
    )

    attr_line_val_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        compute="_compute_attr_line_val_ids",
        string="Allowed Attribute Values",
        help="For normal attributes "
        "the values configured for the product can be selected.\n"
        "For custom attributes the 'Custom' value can also be selected.",
    )

    value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        relation="cfg_line_attr_val_id_rel",
        column1="cfg_line_id",
        column2="attr_val_id",
        string="Values",
    )

    domain_id = fields.Many2one(
        comodel_name="product.config.domain",
        required=True,
        string="Restrictions",
    )

    sequence = fields.Integer(default=10)
