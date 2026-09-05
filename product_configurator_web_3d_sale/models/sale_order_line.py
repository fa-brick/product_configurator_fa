# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Configurer — ou REPRENDRE — depuis une ligne de devis (arbitrage Gerry, 2026-09-05).

Le bouton existe déjà : la roue dentée que `product_configurator_fa_sale` pose
sur chaque ligne configurable d'un devis en brouillon. Comme la clé à molette de
la fiche produit, il ne change ni de place ni d'icône — seulement de
destination.
"""
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def reconfigure_product(self):
        """Ouvrir la configuration 3D de cette ligne.

        Deux cas, et ils ne se ressemblent pas :

        ⓵ **La ligne a déjà une session** — on la ROUVRE, telle quelle. Aucun
        effet de bord : c'est le cas « reprendre », et il doit être aussi sûr
        qu'un lien qu'on rouvre.

        ⓶ **La ligne n'en a pas** — on en crée une, **pré-remplie des valeurs de
        la variante** de la ligne, et on l'attache. ⚠️ Le pré-remplissage n'est
        pas cosmétique : `_compute_price_unit` recalcule le prix de la ligne à
        partir de `config_session_id.price` dès que le lien existe. Une session
        vide mettrait donc la ligne **à zéro**, sans un mot.

        ⚠️ **`force_create=True` ici**, contrairement à la fiche produit : une
        session attachée à une ligne lui appartient. Réutiliser la dernière
        session brouillon du commercial rattacherait à cette ligne-ci une
        configuration déjà portée par une autre.
        """
        self.ensure_one()
        session = self.config_session_id
        if not session:
            session = self.env["product.config.session"].create_get_session(
                self.product_id.product_tmpl_id.id, force_create=True,
            )
            values = self.product_id.product_template_attribute_value_ids
            session.value_ids = [(6, 0, values.product_attribute_value_id.ids)]
            self.config_session_id = session
        return session.action_open_3d_page()
