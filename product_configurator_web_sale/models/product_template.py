# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _website_show_quick_add(self):
        """Pas d'ajout RAPIDE pour ce qui doit d'abord être configuré.

        ⚠️ Ce verrou est en Python, pas dans le gabarit, et c'est délibéré : le
        bouton d'ajout rapide de la vignette vit dans une vue OPTIONNELLE
        (`website_sale.products_add_to_cart`, `active=False` d'origine). Un
        `xpath` sur son contenu casserait tant qu'elle est éteinte, et ne
        protégerait rien tant qu'elle l'est. La méthode, elle, est appelée par
        cette vue quel que soit son état.
        """
        self.ensure_one()
        if self.config_ok:
            return False
        return super()._website_show_quick_add()
