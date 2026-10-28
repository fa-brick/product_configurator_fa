"""Ce que déclare `sale.order` (BO, D-541)."""
# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


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
