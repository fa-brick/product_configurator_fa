"""Ce que déclare `product.price.grid.bracket` (BO, D-541)."""
from odoo import fields, models


class ProductPriceGridBracket(models.Model):
    """Un palier — « jusqu'à 2 500 ».

    En ENREGISTREMENT et non répété sur chaque cellule : sinon corriger un seuil
    de 2 500 à 2 600 demanderait de modifier quinze cellules, et une faute de
    frappe créerait une colonne fantôme (D-083).
    """
    _name = "product.price.grid.bracket"
    _description = "Product Price Grid Bracket"
    _order = "axis, max_value"
    _sql_constraints = [
        (
            "bracket_unique",
            "unique(grid_id, axis, max_value)",
            "Two brackets of the same axis cannot share the same upper bound.",
        )
    ]

    grid_id = fields.Many2one(
        comodel_name="product.price.grid",
        required=True,
        ondelete="cascade",
        index=True,
    )

    axis = fields.Selection(
        selection=[("x", "X (columns)"), ("y", "Y (rows)")],
        required=True,
    )

    max_value = fields.Float(
        string="Up To",
        digits=(16, 4),
        required=True,
        help="Upper bound of the bracket, in the unit of the axis attribute",
    )

    display_name = fields.Char(compute="_compute_display_name")
