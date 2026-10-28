"""Ce qu'exécute `product.attribute.value` (BLL, D-541)."""
from odoo import models


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    def _web_categories(self):
        categories = super()._web_categories()
        publics = self.sudo().product_id.product_tmpl_id.public_categ_ids
        # ⚠️ L'ENFANT FINAL seul : une catégorie ET sa descendante doubleraient la pastille (D-382).
        leaves = publics.filtered(lambda category: not any(
            other != category and other.parent_path.startswith(category.parent_path)
            for other in publics))
        return categories + [{
            "key": "w%s" % category.id,
            "name": category.name,
            "sequence": category.sequence,
            "parent": category.parent_id.name or "",
        } for category in leaves.sorted(lambda c: (c.sequence, c.id))]
