"""Ce que déclare `sale.order.line` (BO, D-541)."""
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # ⓘ Une ligne dupliquée (devis copié) recalcule son plan : le gel appartient à SA commande.
    drawing_attachment_id = fields.Many2one(
        "ir.attachment", string="Frozen drawing", copy=False, readonly=True, ondelete="set null")
