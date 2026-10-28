"""Ce que déclare `product.price.grid.cell` (BO, D-541)."""
from odoo import fields, models


class ProductPriceGridCell(models.Model):
    """Le croisement de deux paliers, et son prix TOTAL."""
    _name = "product.price.grid.cell"
    _description = "Product Price Grid Cell"
    _order = "y_bracket_id, x_bracket_id"
    _sql_constraints = [
        (
            "cell_unique",
            "unique(x_bracket_id, y_bracket_id)",
            "A price is already set for this pair of brackets.",
        )
    ]

    grid_id = fields.Many2one(
        comodel_name="product.price.grid",
        required=True,
        ondelete="cascade",
        index=True,
    )

    x_bracket_id = fields.Many2one(
        comodel_name="product.price.grid.bracket",
        string="X Bracket",
        required=True,
        ondelete="cascade",
        domain="[('grid_id', '=', grid_id), ('axis', '=', 'x')]",
    )

    y_bracket_id = fields.Many2one(
        comodel_name="product.price.grid.bracket",
        string="Y Bracket",
        required=True,
        ondelete="cascade",
        domain="[('grid_id', '=', grid_id), ('axis', '=', 'y')]",
    )

    price = fields.Float(
        string="Total Price",
        digits="Product Price",
        required=True,
        help="Full price for this pair of dimensions — never a supplement",
    )
