"""Ce qu'exécute `ir.actions.report` (BLL, D-541)."""
# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import io
from odoo import models
from odoo.tools.pdf import PdfFileReader, PdfFileWriter


SALE_REPORT = "sale.report_saleorder"


ACTIONS = {
    "portrait": "product_configurator_web_3d_sale_drawing.action_report_drawing_portrait",
    "landscape": "product_configurator_web_3d_sale_drawing.action_report_drawing_landscape",
}


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        """Le PDF du devis reçoit les pages de plan de ses lignes, EN QUEUE (W-118, lot 6).

        ⓘ En queue du flux de `super()` : l'ordre tient avec `sale_pdf_quote_builder`, qui place ses documents de ligne AVANT le corps.
        """
        result = super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)
        if self._get_report(report_ref).report_name != SALE_REPORT or not res_ids:
            return result
        for order in self.env["sale.order"].browse(res_ids):
            entry = result.get(order.id)
            if not entry or not entry.get("stream"):
                continue
            pages = order._drawing_pages()
            if not pages:
                continue
            streams = self._drawing_streams(order, pages)
            if not streams:
                continue
            writer = PdfFileWriter()
            for stream in [entry["stream"], *streams]:
                writer.appendPagesFromReader(PdfFileReader(stream, strict=False))
            merged = io.BytesIO()
            writer.write(merged)
            entry["stream"].close()
            entry["stream"] = merged
        return result

    def _drawing_streams(self, order, pages):
        """Un PDF par suite de pages de même orientation, dans l'ordre des pages.

        ⓘ wkhtmltopdf n'applique qu'UN format par rendu : un rendu par orientation, pas par page (≈ 1 s chacun).
        """
        runs = []
        for page in pages:
            orientation = "landscape" if page["width"] > page["height"] else "portrait"
            if runs and runs[-1][0] == orientation:
                runs[-1][1].append(page["svg"])
            else:
                runs.append((orientation, [page["svg"]]))
        streams = []
        for orientation, svgs in runs:
            pdf, _type = self._render_qweb_pdf(ACTIONS[orientation], res_ids=[order.id], data={"svgs": svgs})
            streams.append(io.BytesIO(pdf))
        return streams
