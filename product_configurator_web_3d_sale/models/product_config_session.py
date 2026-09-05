# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Où la configuration ATTERRIT : la ligne de devis.

C'est la moitié qui manquait — le commercial pouvait ouvrir la page depuis une
ligne, configurer, et rien ne revenait sur le devis. Le prix suivait (le lien
existait), mais la VARIANTE n'était créée que par l'assistant.
"""
from odoo import models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def _web_after_confirm(self):
        """Poser la variante née de la configuration sur la ligne qui l'attend.

        ⚠️ `sudo` : la confirmation passe par une route publique, et l'appelant
        peut être l'utilisateur *public* — celui à qui l'on a donné le lien. Ce
        qui l'autorise est le jeton, pas ses droits.

        ⚠️ **Un devis qui n'est plus en brouillon ne bouge pas.** Une commande
        confirmée porte des engagements — prix, délais, stock : y changer un
        produit parce qu'un lien traînait dans une boîte mail serait un dégât,
        pas un service.

        ⓘ Écrire `product_id` suffit : `name`, taxes et unité se recalculent
        (ce sont des champs calculés `readonly=False` depuis Odoo 17), et le
        prix suit `config_session_id.price` par `_compute_price_unit`.
        """
        res = super()._web_after_confirm()
        lines = self.env["sale.order.line"].sudo().search(
            [("config_session_id", "in", self.ids)]
        )
        for line in lines:
            if line.order_id.state not in ("draft", "sent"):
                continue
            line.product_id = line.config_session_id.product_id
        return res
