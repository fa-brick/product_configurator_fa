# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ProductEnvironmentPlacement(models.Model):
    _inherit = "product.environment.placement"

    # ⓘ Le montage d'un devis = ses placements (E-1) ; vide, le montage est en préparation.
    order_id = fields.Many2one("sale.order", string="Quotation", ondelete="cascade", index=True)
    order_line_id = fields.Many2one("sale.order.line", string="Quotation line", ondelete="set null")
