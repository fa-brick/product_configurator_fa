from odoo import api, models


class ProductProduct(models.Model):
    """Le COÛT d'un produit configuré se recalcule la nuit — D-084.

    ⚠️ `button_bom_cost` est une action MANUELLE : sans disposition, le prix de
    vente suivrait la grille pendant que le coût resterait figé au jour du
    dernier clic. Les marges deviendraient fausses sans erreur ni alerte —
    d'autant plus insidieusement que le prix de vente, lui, serait juste.

    Régime retenu : nocturne sur tout le catalogue configurable. Prévisible, et
    ne dépend d'aucun événement à intercepter. ⚠️ `_compute_bom_price` descend
    RÉCURSIVEMENT dans les sous-nomenclatures : sur un portail à trois niveaux
    ce n'est pas gratuit, et c'est bien pour cela que ce n'est pas un calcul de
    configuration.
    """

    _inherit = "product.product"

    @api.model
    def _cron_refresh_bom_cost(self):
        products = self.search([("config_ok", "=", True)])
        if products:
            products.button_bom_cost()
