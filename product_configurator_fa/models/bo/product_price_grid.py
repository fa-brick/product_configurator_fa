"""Ce que déclare `product.price.grid` (BO, D-541)."""
from odoo import fields, models


class ProductPriceGrid(models.Model):
    """La grille tarifaire d'un produit dimensionné — D-083.

    Par PALIER et non par interpolation : 2 300 prend la colonne « jusqu'à
    2 500 ». Sans surprise pour le client, et un devis se retrouve.

    ⚠️ La cellule porte le prix TOTAL, jamais un supplément. Une grille n'est
    représentable par des `price_extra` que si elle est ADDITIVE — et une vraie
    grille tarifaire ne l'est jamais, c'est même sa raison d'être : sur le
    barème de D-083, l'écart entre deux lignes vaut 40, 50 ou 60 selon la
    colonne.
    """
    _name = "product.price.grid"
    _description = "Product Price Grid"
    _order = "product_tmpl_id, date_start desc, id desc"

    name = fields.Char(required=True)

    active = fields.Boolean(default=True)

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product",
        required=True,
        ondelete="cascade",
        index=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    date_start = fields.Date(
        string="Valid From", help="Empty means valid since forever"
    )

    date_end = fields.Date(string="Valid Until", help="Empty means no end date")

    axis_x_bracket_ids = fields.One2many(
        comodel_name="product.price.grid.bracket",
        inverse_name="grid_id",
        string="X Brackets",
        domain=[("axis", "=", "x")],
        context={"default_axis": "x"},
        copy=True,
    )

    axis_y_bracket_ids = fields.One2many(
        comodel_name="product.price.grid.bracket",
        inverse_name="grid_id",
        string="Y Brackets",
        domain=[("axis", "=", "y")],
        context={"default_axis": "y"},
        copy=True,
    )

    cell_ids = fields.One2many(
        comodel_name="product.price.grid.cell",
        inverse_name="grid_id",
        string="Prices",
        copy=True,
    )
