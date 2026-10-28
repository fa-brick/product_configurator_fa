"""Ce que déclare `product.product` (BO, D-541)."""
from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"
    _rec_name = "config_name"

    grid_price = fields.Float(
        string="Grid Price",
        digits="Product Price",
        readonly=True,
        help="Price read in the grid in force TODAY. Informative only — a "
        "quotation always reads the grid at its own date.",
    )

    config_name = fields.Char(
        string="Configuration Name", compute="_compute_config_name"
    )

    weight_extra = fields.Float(compute="_compute_product_weight_extra")

    weight_dummy = fields.Float(string="Manual Weight", digits="Stock Weight")

    weight = fields.Float(
        compute="_compute_product_weight",
        inverse="_inverse_product_weight",
        search="_search_product_weight",
        store=False,
    )
