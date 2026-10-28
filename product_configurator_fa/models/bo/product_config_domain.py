"""Ce que déclare `product.config.domain` (BO, D-541)."""
from odoo import fields, models


class ProductConfigDomain(models.Model):
    _name = "product.config.domain"
    _description = "Domain for Config Restrictions"

    name = fields.Char(required=True)

    domain_line_ids = fields.One2many(
        comodel_name="product.config.domain.line",
        inverse_name="domain_id",
        string="Restrictions",
        required=True,
        copy=True,
    )

    implied_ids = fields.Many2many(
        comodel_name="product.config.domain",
        relation="product_config_domain_implied_rel",
        string="Inherited",
        column1="domain_id",
        column2="parent_id",
    )

    trans_implied_ids = fields.Many2many(
        comodel_name="product.config.domain",
        # ⚠️ La méthode se cite par son NOM : citée par objet, elle devrait précéder le champ dans la même classe (D-541).
        compute="_get_trans_implied",
        column1="domain_id",
        column2="parent_id",
        string="Transitively inherits",
    )
