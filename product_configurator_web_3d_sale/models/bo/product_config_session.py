"""Ce que déclare `product.config.session` (BO, D-541)."""
from odoo import fields, models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    # ⚠️ Sans eux, la fenêtre ouverte depuis un devis afficherait le prix de la liste du
    # commercial, et la ligne celui du devis : deux montants pour une configuration (D-537).
    order_pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        string="Quotation Pricelist",
        help="Pricelist of the quotation this configuration was opened from.",
    )

    order_date = fields.Datetime(
        string="Quotation Date",
        help="Date of the quotation this configuration was opened from: its price grid applies.",
    )
