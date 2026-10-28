"""Ce qu'exécute `product.config.session` (BLL, D-541).

Le total de la page, TTC ou HT selon le réglage du site — W-100, lot 2 (D-396).
"""
from odoo import models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def _web_displayed_price(self, unit_price, product):
        """Taxer le prix affiché sur le SITE, comme la boutique d'Odoo (`_get_sales_prices`).

        ⚠️ Hors du site (dialogue du devis, éditeur), le prix reste HT : il n'y a pas de réglage de site à suivre (D-396).
        ⚠️ Les taxes de l'ARTICLE, après position fiscale : une ligne à part n'a pas forcément celles du produit (D-396).
        """
        unit_price = super()._web_displayed_price(unit_price, product)
        if not self.env.context.get("cfg_on_site") or not product:
            return unit_price
        website = self.env["website"].get_current_website()
        if not website:
            return unit_price
        product = product.sudo()
        product_taxes = product.taxes_id._filter_taxes_by_company(self.env.company)
        if not product_taxes:
            return unit_price
        taxes = website.fiscal_position_id.sudo().map_tax(product_taxes)
        return self.env["product.template"]._apply_taxes_to_price(
            unit_price, self._web_currency(), product_taxes, taxes, product, website=website)
