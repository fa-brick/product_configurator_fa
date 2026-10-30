"""Ce que déclare `res.config.settings` (BO, D-541)."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ⚠️ `translate=False` : le bouton de langue des paramètres ne fait rien, la page se recharge en enregistrant (D-558).
    # ⓘ Saisi ici, le texte vaut pour la langue de l'utilisateur ; les autres se traduisent sur la fiche du site web.
    website_configure_button_text = fields.Char(
        related="website_id.configure_button_text", readonly=False, translate=False)
