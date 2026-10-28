"""Ce qu'exécute `product.attribute.bound` (BLL, D-541)."""
from odoo import api, models


class ProductAttributeBound(models.Model):
    _inherit = "product.attribute.bound"

    @api.depends("domain_id")
    def _compute_display_name(self):
        for bound in self:
            bound.display_name = bound.domain_id.name or self.env._("Bound")
