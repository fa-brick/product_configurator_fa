"""Ce qu'exécute `product.price.grid.cell` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductPriceGridCell(models.Model):
    _inherit = "product.price.grid.cell"

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
