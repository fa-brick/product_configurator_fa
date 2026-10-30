"""Ce que déclare `website` (BO, D-541)."""
from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    # ⓘ Vide, le bouton dit « Configure » traduit dans la langue du visiteur : `_configure_button_label` (D-558).
    configure_button_text = fields.Char(
        string="Configure button text",
        translate=True,
        help="Text of the button that opens the configurator: product page, shop grid, wishlist. "
             "Empty, the button says \"Configure\" in the visitor's language.",
    )
