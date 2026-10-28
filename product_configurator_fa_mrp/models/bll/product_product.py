"""Ce qu'exécute `product.product` (BLL, D-541)."""
from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _cron_refresh_bom_cost(self):
        products = self.search([("config_ok", "=", True)])
        if products:
            products.button_bom_cost()
