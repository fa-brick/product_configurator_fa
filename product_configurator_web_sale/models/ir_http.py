# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        """Les traductions JS de la fenêtre des optionnels, servies au site.

        ⚠️ Hors de cette liste, aucune chaîne `_t()` du module n'est traduite sur le site (L-394).
        """
        mods = super()._get_translation_frontend_modules_name()
        return mods + ["product_configurator_web_sale"]
