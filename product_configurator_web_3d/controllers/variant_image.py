# -*- coding: utf-8 -*-
"""La route qui reçoit l'image d'une variante née d'une configuration — D-399, lot 5.

⚠️ PUBLIQUE, comme ses sœurs : le JETON est le seul contrôle (`_session`), et toutes les
gardes sur l'image et la variante vivent dans le modèle
(`product.config.session.web_store_variant_image`), testées là.
"""
from odoo import http

from .main import ProductConfiguratorWeb3D


class ProductConfiguratorVariantImage(ProductConfiguratorWeb3D):

    @http.route(
        "/configurator/variant_image", type="json", auth="public", methods=["POST"],
        website=False, csrf=False,
    )
    def variant_image(self, token=None, holder=None, product_id=None, image=None, **kwargs):
        """L'image que le navigateur du client a prise à la confirmation.

        ⓘ Pas de MAIN demandée : la session est CLOSE quand l'image arrive — c'est la
        confirmation qui a fait naître la variante —, et la main est rendue avec elle.
        """
        session = self._session(token, holder)
        if not session:
            return {"error": "unknown_session"}
        return session.web_store_variant_image(product_id, image)
