# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    config_ok = fields.Boolean(
        related="product_id.config_ok",
        store=True,
        string="Configurable",
        readonly=True,
    )
    config_session_id = fields.Many2one(
        comodel_name="product.config.session", string="Config Session"
    )
    custom_value_ids = fields.One2many(
        comodel_name="product.config.session.custom.value",
        inverse_name="cfg_session_id",
        related="config_session_id.custom_value_ids",
        string="Custom Values",
    )

    # ⓘ **`action_config_start` ET `reconfigure_product` ONT DISPARU** — arbitrage
    # Gerry, 2026-09-19 : *« pour moi le wizard est mort, on peut le supprimer. »*
    #
    # Les deux n'existaient que pour ouvrir l'assistant OCA : la première depuis un
    # bouton injecté dans toutes les listes du back-office, la seconde depuis un bouton
    # « Reconfigure » du formulaire. Le configurateur 3D les remplace toutes les deux, et
    # `product_configurator_web_3d_mrp` l'ouvre au moment où l'on CHOISIT le produit —
    # ce qui supprime le besoin d'un bouton.
    #
    # ⚠️ `config_session_id` reste : c'est le lien vers la configuration, et le
    # configurateur 3D l'écrit comme le faisait le wizard. Ce n'est pas lui qui meurt.


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    config_ok = fields.Boolean(
        related="product_tmpl_id.config_ok",
        store=True,
        string="Configurable",
        readonly=True,
    )


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    config_set_id = fields.Many2one(
        comodel_name="mrp.bom.line.configuration.set",
        string="Configuration Set",
    )


class MrpBomLineConfigurationSet(models.Model):
    _name = "mrp.bom.line.configuration.set"
    _description = "Mrp Bom Line Configuration Set"

    name = fields.Char(string="Configuration", required=True)
    configuration_ids = fields.One2many(
        comodel_name="mrp.bom.line.configuration",
        inverse_name="config_set_id",
        string="Configurations",
    )
    bom_line_ids = fields.One2many(
        comodel_name="mrp.bom.line",
        inverse_name="config_set_id",
        string="BoM Lines",
        readonly=True,
    )


class MrpBomLineConfiguration(models.Model):
    _name = "mrp.bom.line.configuration"
    _description = "Mrp Bom Line Configuration"

    config_set_id = fields.Many2one(
        comodel_name="mrp.bom.line.configuration.set",
        ondelete="cascade",
        required=True,
    )
    value_ids = fields.Many2many(
        string="Attribute Values",
        comodel_name="product.attribute.value",
        required=True,
    )
