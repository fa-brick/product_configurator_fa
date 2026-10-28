"""Ce que déclare `product.config.session.custom.value` (BO, D-541)."""
from odoo import fields, models


class ProductConfigSessionCustomValue(models.Model):
    _name = "product.config.session.custom.value"
    _description = "Product Config Session Custom Value"
    _rec_name = "attribute_id"

    name = fields.Char(readonly=True, compute="_compute_val_name", store=True)

    attribute_id = fields.Many2one(
        comodel_name="product.attribute", string="Attribute", required=True
    )

    cfg_session_id = fields.Many2one(
        comodel_name="product.config.session",
        required=True,
        ondelete="cascade",
        string="Session",
    )

    value = fields.Char(help="Custom value held as string")

    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="product_config_session_custom_value_attachment_rel",
        column1="cfg_sesion_custom_val_id",
        column2="attachment_id",
        string="Attachments",
    )
