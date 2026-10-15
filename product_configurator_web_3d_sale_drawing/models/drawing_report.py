# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from markupsafe import Markup

from odoo import api, models


class DrawingPageReport(models.AbstractModel):
    # ⚠️ Un nom COURT : la table du modèle, `report_<module>_<gabarit>`, ne dépasse pas 63 caractères.
    _name = "report.product_configurator_web_3d_sale_drawing.pages"
    _description = "Dimensioned drawing pages"

    @api.model
    def _get_report_values(self, docids, data=None):
        # ⓘ Des SVG que le MOTEUR a écrits, ses textes échappés (`page_svg.js`) : ils s'insèrent tels quels.
        return {"svgs": [Markup(svg) for svg in (data or {}).get("svgs") or []]}
