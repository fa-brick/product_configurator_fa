# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import Command, models


class SaleOrder(models.Model):
    """Le panier du site, LIÉ à la configuration qui a fait naître l'article — W-99 / D-393 (Q2).

    La page du configurateur met l'article au panier par `/shop/cart/update_json`, en passant le
    jeton de sa session (`config_session_token`). Odoo, laissé à lui-même, recomposerait la
    combinaison depuis l'article et les réponses reçues — et compléterait d'office chaque question
    « sans variante » par sa PREMIÈRE valeur. Avec le jeton, la ligne :

    - garde l'article TEL QUEL (celui que la confirmation a créé) ;
    - porte sa configuration (`config_session_id`) — donc le PRIX de la configuration
      (`product_configurator_fa_sale`), et la réouverture d'un devis (D-371) ;
    - porte les réponses « sans variante » de la session.

    Une configuration = une ligne : ajoutée deux fois, sa quantité monte ; deux configurations
    qui ne diffèrent que par une réponse « sans variante » ont DEUX lignes, bien que l'article
    soit le même. Sans jeton, rien ne change.
    """

    _inherit = "sale.order"

    def _configurator_session(self, token, product_id):
        """La session de ce jeton, si c'est bien elle qui a fait naître CET article.

        ⓘ `sudo` : le visiteur n'a aucun droit sur les sessions ; le contrôle est le jeton, comme
        sur les routes de la page. L'article doit être le sien, sans quoi un jeton valable
        rattacherait n'importe quel article à n'importe quelle configuration.
        """
        Session = self.env["product.config.session"].sudo()
        if not token:
            return Session
        session = Session._find_by_access_token(token)
        if not session or session.product_id.id != product_id:
            return Session
        return session

    def _cart_find_product_line(self, product_id, line_id=None, config_session_token=None, **kwargs):
        session = self._configurator_session(config_session_token, product_id)
        if not session or line_id:
            return super()._cart_find_product_line(product_id, line_id=line_id, **kwargs)
        linked_line_id = kwargs.get("linked_line_id") or False
        return self.order_line.filtered(
            lambda line: line.product_id.id == product_id
            and line.config_session_id == session
            and line.linked_line_id.id == (linked_line_id or False)
        )

    def _prepare_order_line_values(self, product_id, quantity, config_session_token=None, **kwargs):
        session = self._configurator_session(config_session_token, product_id)
        if not session:
            return super()._prepare_order_line_values(product_id, quantity, **kwargs)
        values = {
            "product_id": product_id,
            "product_uom_qty": quantity,
            "order_id": self.id,
            "linked_line_id": kwargs.get("linked_line_id") or False,
            "config_session_id": session.id,
        }
        ptav_ids = session._web_no_variant_ptav_ids()
        if ptav_ids:
            values["product_no_variant_attribute_value_ids"] = [Command.set(ptav_ids)]
        return values
