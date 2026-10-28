"""Ce que déclare `mrp.bom.line` (BO, D-541)."""
from odoo import fields, models


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    config_set_id = fields.Many2one(
        comodel_name="mrp.bom.line.configuration.set",
        string="Configuration Set",
    )
