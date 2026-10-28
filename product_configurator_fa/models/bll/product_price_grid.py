"""Ce qu'exécute `product.price.grid` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductPriceGrid(models.Model):
    _inherit = "product.price.grid"

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
