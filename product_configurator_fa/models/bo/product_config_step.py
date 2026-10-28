"""Ce que déclare `product.config.step` (BO, D-541)."""
from odoo import fields, models


class ProductConfigStep(models.Model):
    _name = "product.config.step"
    _description = "Product Config Steps"

    # TODO: Prevent values which have dependencies to be set in a
    #       step with higher sequence than the dependency
    name = fields.Char(required=True, translate=True)
