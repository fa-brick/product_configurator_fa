# -*- coding: utf-8 -*-
"""Le dialogue de vente d'Odoo reçoit ce que dessinent la carte et la grande pastille — D-563.

ⓘ Le dialogue du devis et celui des options du site passent tous deux par `_get_product_information`.
"""
from odoo.http import request

from odoo.addons.sale.controllers.product_configurator import SaleProductConfiguratorController


class SaleProductConfiguratorImageForms(SaleProductConfiguratorController):

    def _get_product_information(self, *args, **kwargs):
        """⚠️ Chaque clé ajoutée ici est déclarée au `shape` des props (`sale_card_tolerance.js`), sinon OWL refuse
        le composant en mode développeur (D-563)."""
        info = super()._get_product_information(*args, **kwargs)
        Attribute = request.env["product.attribute"]
        Ptav = request.env["product.template.attribute.value"]
        for line in info["attribute_lines"]:
            attribute = Attribute.browse(line["attribute"]["id"])
            line["attribute"].update(swatch_mark=attribute.swatch_mark, answer_size=attribute.answer_size)
            for value in line["attribute_values"]:
                value["preview"] = Ptav.browse(value["id"]).product_attribute_value_id._preview_url()
        return info
