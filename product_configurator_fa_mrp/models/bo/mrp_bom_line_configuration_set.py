"""Ce que déclare `mrp.bom.line.configuration.set` (BO, D-541)."""
from odoo import fields, models


class MrpBomLineConfigurationSet(models.Model):
    _name = "mrp.bom.line.configuration.set"
    _description = "Mrp Bom Line Configuration Set"

    name = fields.Char(string="Configuration", required=True)

    configuration_ids = fields.One2many(
        comodel_name="mrp.bom.line.configuration",
        inverse_name="config_set_id",
        string="Configurations",
    )

    bom_line_ids = fields.One2many(
        comodel_name="mrp.bom.line",
        inverse_name="config_set_id",
        string="BoM Lines",
        readonly=True,
    )
