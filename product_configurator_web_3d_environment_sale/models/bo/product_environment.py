"""Ce que déclare `product.environment` (BO, D-541)."""
# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ProductEnvironment(models.Model):
    _inherit = "product.environment"

    order_ids = fields.One2many("sale.order", "environment_id", string="Quotations")

    # ⓘ Le chantier dont cette copie est née pour un devis (8.5c-d) : reprendre le projet par le jeton du
    # chantier retrouve le devis en cours qui lit cette copie, et le portail ne la liste pas à part.
    source_environment_id = fields.Many2one("product.environment", string="Copied from", copy=False,
                                            index=True, ondelete="set null")
