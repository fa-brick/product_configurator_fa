"""Ce que déclare `product.attribute.value` (BO, D-541)."""
from odoo import models


class ProductAttributeValue(models.Model):
    """La réponse qui désigne un PRODUIT se range sous ses catégories E-COMMERCE — D-382.

    ⓘ **Ici, et pas dans `product_configurator_web_3d`** : la page ne dépend pas de
    `website_sale` (voir le manifeste). La catégorie e-commerce ne s'ajoute donc que là
    où la boutique est installée ; ailleurs, la réponse tombe dans « Autres ».

    ⓘ **E-commerce, et non la catégorie de produit** (D-382) : son nom se traduit et se
    range par séquence. `categ_id` est interne (comptabilité, stock : « Saleable »).
    """
    _inherit = "product.attribute.value"
