# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


# ⓘ **`sale.order.action_config_start` A DISPARU** — arbitrage Gerry, 2026-09-19 :
# *« pour moi le wizard est mort, on peut le supprimer. »* Elle n'existait que pour
# ouvrir l'assistant OCA depuis un bouton « Configure Product » au-dessus des lignes,
# lui-même retiré. Le configurateur 3D s'ouvre désormais au CHOIX du produit sur la
# ligne, ce qui ne demande plus de bouton.


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    custom_value_ids = fields.One2many(
        comodel_name="product.config.session.custom.value",
        inverse_name="cfg_session_id",
        related="config_session_id.custom_value_ids",
        string="Configurator Custom Values",
    )
    config_ok = fields.Boolean(
        related="product_id.config_ok", string="Configurable", readonly=True
    )
    config_session_id = fields.Many2one(
        comodel_name="product.config.session", string="Config Session"
    )

    # ⓘ **`reconfigure_product` A DISPARU D'ICI**, et elle n'a pas disparu tout court :
    # `product_configurator_web_3d_sale` en donne sa propre version, qui ouvre la page 3D
    # de la ligne. Celle-ci ne faisait qu'ouvrir l'assistant OCA, et la remplaçait déjà
    # sans l'appeler — la garder ne laissait qu'un corps mort sous un nom vivant.

    @api.depends(
        "config_session_id",
        "tax_id",
        "company_id",
    )
    def _compute_price_unit(self):
        result = None
        for line in self:
            if line.config_session_id:
                account_tax_obj = self.env["account.tax"]
                line.price_unit = account_tax_obj._fix_tax_included_price_company(
                    line.config_session_id.price,
                    line.product_id.taxes_id,
                    line.tax_id,
                    line.company_id,
                )
            else:
                result = super(SaleOrderLine, line)._compute_price_unit()
        return result

    def _get_sale_order_line_multiline_description_variants(self):
        name = ""
        for line in self:
            custom_values = line.custom_value_ids
            if custom_values:
                name += "\n" + "\n".join(
                    [f"{cv.display_name}: {cv.value}" for cv in custom_values]
                )
            else:
                name += super(
                    SaleOrderLine,
                    line,
                )._get_sale_order_line_multiline_description_variants()
        return name
