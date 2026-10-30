"""Ce qu'exécute `product.product` (BLL, D-541).

La description de vente d'un article CONFIGURÉ : son nom, puis une réponse par ligne — D-555.
"""
from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def get_product_multiline_description_sale(self):
        """Le nom de l'article, une ligne « Question: réponse » par choix, puis la description de vente.

        ⚠️ Pas les réponses entre parenthèses du nom de variante : au panier et au devis, ce titre devient illisible (D-555).
        ⓘ Les seules questions à choix, comme le nom de variante d'Odoo (`_get_combination_name`).
        ⓘ La réponse se lit avec son unité : `display_name` de la valeur, pas son `name` nu (D-160).
        """
        if not self.config_ok:
            return super().get_product_multiline_description_sale()
        self.ensure_one()
        name = self.name
        if self.env.context.get("display_default_code", True) and self.default_code:
            name = f"[{self.default_code}] {name}"
        lines = [name] + self._configured_answer_lines()
        if self.description_sale:
            lines.append(self.description_sale)
        return "\n".join(lines)

    def _configured_answer_lines(self):
        """Une ligne « Question: réponse » par question à choix de la variante — la liste de souhaits la montre aussi (D-557)."""
        self.ensure_one()
        answers = self.product_template_attribute_value_ids \
            ._without_no_variant_attributes()._filter_single_value_lines()
        return [ptav.product_attribute_value_id.with_context(show_attribute=True).display_name
                for ptav in answers]
