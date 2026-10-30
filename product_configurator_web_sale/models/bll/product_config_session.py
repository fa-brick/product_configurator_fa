"""Ce qu'exécute `product.config.session` (BLL, D-541).

Le total de la page, TTC ou HT selon le réglage du site — W-100, lot 2 (D-396).
Ce que fait le bouton de fin de la page : mettre au panier, ou seulement confirmer — D-553.
Une configuration déjà au panier y retourne une fois confirmée — D-556.
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

    def web_state(self):
        """L'état de la page, plus ce que fait son bouton de fin : mettre au panier ou confirmer."""
        state = super().web_state()
        state["cart"] = self._web_goes_to_cart()
        state["inCart"] = self._web_is_in_cart()
        return state

    def _web_is_in_cart(self):
        """La configuration a-t-elle déjà sa ligne dans un panier du site ? La confirmer y ramène — D-556.

        ⚠️ Un devis du back-office n'est pas un panier : son lien reçu par courriel ne mène pas à `/shop/cart` (D-556).
        """
        self.ensure_one()
        if not self.env.context.get("cfg_on_site"):
            return False
        return any(line.order_id.website_id and line.order_id.state == "draft"
                   for line in self._quote_lines())

    def _web_goes_to_cart(self):
        """La confirmation met-elle au panier ? Sur le site, quel que soit le chemin d'arrivée.

        ⚠️ Lire ceci sur la session, pas sur l'hôte : la page atteinte par lien ou rechargement confirmait sans rien mettre au panier (D-553).
        ⚠️ Pas de panier hors du site : le dialogue du devis monte la même page (D-396).
        ⚠️ Pas de panier pour une session qui a déjà sa ligne : `_web_after_confirm` la met à jour, l'ajout la doublerait (D-553).
        """
        self.ensure_one()
        return bool(self.env.context.get("cfg_on_site")) and not self._quote_lines()
