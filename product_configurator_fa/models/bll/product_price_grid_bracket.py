"""Ce qu'exécute `product.price.grid.bracket` (BLL, D-541)."""
from odoo import api, models


class ProductPriceGridBracket(models.Model):
    _inherit = "product.price.grid.bracket"

    @api.depends("max_value")
    def _compute_display_name(self):
        for bracket in self:
            value = bracket.max_value
            if float(value).is_integer():
                shown = str(int(value))
            else:
                shown = f"{value:.4f}".rstrip("0").rstrip(".")
            bracket.display_name = f"≤ {shown}"
