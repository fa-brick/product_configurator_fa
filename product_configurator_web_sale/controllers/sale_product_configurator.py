# -*- coding: utf-8 -*-
"""Le dialogue de vente reçoit la forme et la vignette des réponses, boutique installée — D-563."""
from odoo.addons.product_configurator_web_3d.controllers.sale_product_configurator import (
    SaleProductConfiguratorImageForms,
)
from odoo.addons.website_sale.controllers.product_configurator import (
    WebsiteSaleProductConfiguratorController,
)


class WebsiteSaleProductConfiguratorImageForms(SaleProductConfiguratorImageForms,
                                               WebsiteSaleProductConfiguratorController):
    """⚠️ La classe de `website_sale` descend aussi du portail : l'arbre du portail fusionne sa propre copie, sans
    `SaleProductConfiguratorImageForms`, et c'est elle qui sert la route (D-563).
    ⓘ Héritière des deux, cette classe est la feuille commune aux deux arbres : un seul passage par l'ajout."""
