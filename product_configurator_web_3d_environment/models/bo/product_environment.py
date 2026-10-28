"""Ce que déclare `product.environment` (BO, D-541)."""
# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ProductEnvironment(models.Model):
    _inherit = "product.environment"

    placement_ids = fields.One2many("product.environment.placement", "environment_id", string="Placed products")
