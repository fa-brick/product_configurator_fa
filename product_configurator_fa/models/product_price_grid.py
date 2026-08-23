from odoo import api, fields, models
from odoo.exceptions import ValidationError


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

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for grid in self:
            if grid.date_start and grid.date_end and grid.date_end < grid.date_start:
                raise ValidationError(
                    self.env._("The end date must come after the start date")
                )

    @api.constrains("product_tmpl_id", "date_start", "date_end", "active")
    def _check_no_overlap(self):
        """Une seule grille en vigueur à une date donnée, pour un produit.

        Odoo tranche ses listes de prix concurrentes par un tri ; ici on préfère
        **interdire l'ambiguïté** plutôt que de se demander après coup laquelle a
        gagné (D-083).
        """
        for grid in self.filtered("active"):
            others = self.search(
                [
                    ("product_tmpl_id", "=", grid.product_tmpl_id.id),
                    ("id", "!=", grid.id),
                ]
            )
            for other in others:
                after = (
                    grid.date_start
                    and other.date_end
                    and grid.date_start > other.date_end
                )
                before = (
                    grid.date_end
                    and other.date_start
                    and grid.date_end < other.date_start
                )
                if not after and not before:
                    raise ValidationError(
                        self.env._(
                            "Price grid '%(grid)s' overlaps with '%(other)s' on the "
                            "same product. Only one grid may be in force at a time.",
                            grid=grid.name,
                            other=other.name,
                        )
                    )

    @api.model_create_multi
    def create(self, vals_list):
        grids = super().create(vals_list)
        grids.product_tmpl_id._refresh_grid_list_price()
        return grids

    def write(self, vals):
        result = super().write(vals)
        self.product_tmpl_id._refresh_grid_list_price()
        return result

    def _bracket_for(self, axis, value):
        """Le premier palier qui ENCADRE la valeur, ou rien au-delà du dernier."""
        self.ensure_one()
        brackets = self.axis_x_bracket_ids if axis == "x" else self.axis_y_bracket_ids
        for bracket in brackets.sorted("max_value"):
            if value <= bracket.max_value:
                return bracket
        return brackets.browse()

    def get_price(self, x_value, y_value):
        """Rend le prix TOTAL pour ce couple de dimensions, ou `None`.

        `None` dit « hors grille » et n'est pas un prix de zéro : c'est un cas
        que l'appelant doit SIGNALER, jamais absorber (D-083).
        """
        self.ensure_one()
        x_bracket = self._bracket_for("x", x_value)
        y_bracket = self._bracket_for("y", y_value)
        if not x_bracket or not y_bracket:
            return None
        cell = self.cell_ids.filtered(
            lambda c, x=x_bracket, y=y_bracket: c.x_bracket_id == x
            and c.y_bracket_id == y
        )
        return cell[:1].price if cell else None

    def _lowest_price(self):
        """Le « à partir de » du produit — D-093."""
        self.ensure_one()
        prices = self.cell_ids.mapped("price")
        return min(prices) if prices else 0.0


class ProductPriceGridBracket(models.Model):
    """Un palier — « jusqu'à 2 500 ».

    En ENREGISTREMENT et non répété sur chaque cellule : sinon corriger un seuil
    de 2 500 à 2 600 demanderait de modifier quinze cellules, et une faute de
    frappe créerait une colonne fantôme (D-083).
    """

    _name = "product.price.grid.bracket"
    _description = "Product Price Grid Bracket"
    _order = "axis, max_value"

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

    _sql_constraints = [
        (
            "bracket_unique",
            "unique(grid_id, axis, max_value)",
            "Two brackets of the same axis cannot share the same upper bound.",
        )
    ]

    @api.depends("max_value")
    def _compute_display_name(self):
        for bracket in self:
            value = bracket.max_value
            if float(value).is_integer():
                shown = str(int(value))
            else:
                shown = f"{value:.4f}".rstrip("0").rstrip(".")
            bracket.display_name = f"≤ {shown}"


class ProductPriceGridCell(models.Model):
    """Le croisement de deux paliers, et son prix TOTAL."""

    _name = "product.price.grid.cell"
    _description = "Product Price Grid Cell"
    _order = "y_bracket_id, x_bracket_id"

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

    _sql_constraints = [
        (
            "cell_unique",
            "unique(x_bracket_id, y_bracket_id)",
            "A price is already set for this pair of brackets.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        cells = super().create(vals_list)
        cells.grid_id.product_tmpl_id._refresh_grid_list_price()
        return cells

    def write(self, vals):
        result = super().write(vals)
        # Le « à partir de » du produit est le minimum de la grille : changer
        # une cellule peut le déplacer (D-093).
        self.grid_id.product_tmpl_id._refresh_grid_list_price()
        return result

    @api.constrains("grid_id", "x_bracket_id", "y_bracket_id")
    def _check_brackets_belong_to_grid(self):
        for cell in self:
            if cell.x_bracket_id.grid_id != cell.grid_id:
                raise ValidationError(
                    self.env._("The X bracket belongs to another grid")
                )
            if cell.y_bracket_id.grid_id != cell.grid_id:
                raise ValidationError(
                    self.env._("The Y bracket belongs to another grid")
                )
            if cell.x_bracket_id.axis != "x" or cell.y_bracket_id.axis != "y":
                raise ValidationError(self.env._("Brackets are on the wrong axis"))
