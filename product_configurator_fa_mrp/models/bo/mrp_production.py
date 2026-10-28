"""Ce que déclare `mrp.production` (BO, D-541)."""
# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    config_session_id = fields.Many2one(
        comodel_name="product.config.session", string="Config Session"
    )

    custom_value_ids = fields.One2many(
        comodel_name="product.config.session.custom.value",
        inverse_name="cfg_session_id",
        related="config_session_id.custom_value_ids",
        string="Custom Values",
    )
    # ⓘ Ni `action_config_start` ni `reconfigure_product` : le configurateur 3D s'ouvre au
    # CHOIX du produit, par `product_configurator_web_3d_mrp`.
    # ⚠️ Ne pas retirer `config_session_id` : le configurateur 3D y écrit le lien vers la
    # configuration.
