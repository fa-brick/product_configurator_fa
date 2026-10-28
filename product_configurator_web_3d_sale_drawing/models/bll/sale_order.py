"""Ce qu'exécute `sale.order` (BLL, D-541)."""
# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging
from odoo import _, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        """La commande GÈLE le plan de chaque ligne (D-468).

        ⚠️ Une panne du moteur ne bloque PAS la confirmation : elle se journalise et se note sur le devis, et le gel se retente à la lecture suivante (D-468).
        """
        result = super()._action_confirm()
        for order in self.sudo():
            failed = order.env["sale.order.line"]
            for line in order.order_line.filtered(lambda l: not l.drawing_attachment_id and l._drawing_template()):
                try:
                    pages = line._drawing_compute()
                except Exception:
                    _logger.exception("drawing of sale order line %s could not be frozen", line.id)
                    pages = None
                if pages is None:
                    _logger.error("drawing of sale order line %s (%s) could not be frozen: engine failure",
                                  line.id, order.name)
                    failed |= line
                elif pages:
                    line._drawing_store(pages)
            if failed:
                order.message_post(
                    body=_("The dimensioned drawing of %(products)s could not be drawn at confirmation."
                           " It will be drawn again the next time the quotation is printed.",
                           products=", ".join(failed.mapped("product_id.display_name"))),
                    message_type="comment", subtype_xmlid="mail.mt_note")
        return result

    def _drawing_pages(self):
        """Les pages de plan du devis, ligne par ligne, dans l'ordre des lignes."""
        self.ensure_one()
        pages = []
        for line in self.order_line:
            if line._drawing_template():
                pages.extend(line._drawing_pages() or [])
        return pages
