"""Ce que déclare `mrp.bom` (BO, D-541)."""
from odoo import fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    config_ok = fields.Boolean(
        related="product_tmpl_id.config_ok",
        store=True,
        string="Configurable",
        readonly=True,
    )
