"""Ce qu'exécute `report.product_configurator_web_3d_sale_drawing.pages` (BLL, D-541)."""
from markupsafe import Markup
from odoo import api, models


class DrawingPageReport(models.AbstractModel):
    _inherit = "report.product_configurator_web_3d_sale_drawing.pages"

    @api.model
    def _get_report_values(self, docids, data=None):
        # ⓘ Des SVG que le MOTEUR a écrits, ses textes échappés (`page_svg.js`) : ils s'insèrent tels quels.
        return {"svgs": [Markup(svg) for svg in (data or {}).get("svgs") or []]}
