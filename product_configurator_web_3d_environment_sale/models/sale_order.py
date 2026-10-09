# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ⓘ L'environnement que le MONTAGE de ce devis lit (E-1) ; un devis dupliqué n'emporte pas de montage.
    environment_id = fields.Many2one("product.environment", string="Environment", copy=False, index=True)
    environment_placement_ids = fields.One2many("product.environment.placement", "order_id", string="Montage")
