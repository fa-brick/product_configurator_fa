# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        """Les traductions JS de la PAGE du configurateur, servies au site.

        ⚠️ **Sur le site, Odoo ne charge les chaînes JS que d'une LISTE de modules** —
        `web`, `portal`, les `website*` (`http_routing`, `website/models/ir_http.py`).
        Ce module n'y figurait pas : aucune chaîne de la page n'était jamais traduite, et
        un « 12 characters max » s'affichait sous une page française (relevé le
        2026-09-25, D-353). Le `fr.po` était juste ; c'est le chargeur qui ne le lisait
        pas. Même geste que `portal`.
        """
        mods = super()._get_translation_frontend_modules_name()
        return mods + ["product_configurator_web_3d"]
