"""Ce que déclare `mrp.bom.line.configuration` (BO, D-541)."""
from odoo import fields, models


class MrpBomLineConfiguration(models.Model):
    _name = "mrp.bom.line.configuration"
    _description = "Mrp Bom Line Configuration"

    config_set_id = fields.Many2one(
        comodel_name="mrp.bom.line.configuration.set",
        ondelete="cascade",
        required=True,
    )

    value_ids = fields.Many2many(
        string="Attribute Values",
        comodel_name="product.attribute.value",
        required=True,
    )
