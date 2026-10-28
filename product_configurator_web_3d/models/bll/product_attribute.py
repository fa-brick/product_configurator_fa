"""Ce qu'exécute `product.attribute` (BLL, D-541)."""
from odoo import models


# Les formes qui montrent une IMAGE, et celles qu'une ligne résumé peut remplacer (D-382).
IMAGE_FORMS = ("card", "swatch")


SUMMARY_FORMS = ("card", "swatch", "radio", "pills", "select")


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    def _web_answer_layout(self):
        """La disposition EFFECTIVE, telle que la page la reçoit — D-382.

        ⓘ Le miroir de `answerLayoutOf` (`configurator_state.js`) : le serveur sert la
        disposition déjà ramenée à ce que la forme permet, la page refait le même calcul
        pour un serveur qui ne la servirait pas encore.
        """
        self.ensure_one()
        layout = self.answer_layout or "inline"
        if layout in ("scroll", "line") and self.display_type not in IMAGE_FORMS:
            return "inline"
        if layout == "summary" and self.display_type not in SUMMARY_FORMS:
            return "inline"
        return layout
