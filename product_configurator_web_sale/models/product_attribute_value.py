from odoo import models


class ProductAttributeValue(models.Model):
    """La réponse qui désigne un PRODUIT se range sous ses catégories E-COMMERCE — D-382.

    ⓘ **Ici, et pas dans `product_configurator_web_3d`** : la page ne dépend pas de
    `website_sale` (voir le manifeste). La catégorie e-commerce ne s'ajoute donc que là
    où la boutique est installée ; ailleurs, la réponse tombe dans « Autres ».

    ⓘ **E-commerce, et non la catégorie de produit** (Gerry, 2026-09-30) : son nom se
    traduit et se range par séquence — elle est faite pour le client. `categ_id` est
    interne (comptabilité, stock : « Saleable », « Office Furniture »).
    """

    _inherit = "product.attribute.value"

    def _web_categories(self):
        categories = super()._web_categories()
        publics = self.sudo().product_id.product_tmpl_id.public_categ_ids
        # ⚠️ **L'ENFANT FINAL seul** (Gerry) : un produit rangé dans « Châssis » ET dans
        # « Châssis / Plaque caméra » ne se montre que sous la seconde — la première n'en dit
        # pas plus, et doublerait la pastille.
        leaves = publics.filtered(lambda category: not any(
            other != category and other.parent_path.startswith(category.parent_path)
            for other in publics))
        return categories + [{
            "key": "w%s" % category.id,
            "name": category.name,
            "sequence": category.sequence,
            "parent": category.parent_id.name or "",
        } for category in leaves.sorted(lambda c: (c.sequence, c.id))]
