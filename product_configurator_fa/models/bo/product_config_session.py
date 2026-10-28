"""Ce que déclare `product.config.session` (BO, D-541)."""
from odoo import fields, models


class ProductConfigSession(models.Model):
    # ⚠️ `mail.thread` : une session passe de main en main — un particulier, un
    # professionnel, un commercial. Savoir qui a changé quoi et quand n'est pas
    # un luxe (D-092). OCA n'en avait aucune trace.
    _name = "product.config.session"
    _description = "Product Config Session"
    # ⓘ `bus.listener.mixin` : une session est un objet qu'on REGARDE à
    # plusieurs (D-253). Le mixin lui donne son canal ; qui diffuse et
    # quoi reste au module d'interface.
    _inherit = ["mail.thread", "bus.listener.mixin"]

    name = fields.Char(string="Configuration Session Number", readonly=True)

    product_id = fields.Many2one(
        comodel_name="product.product",
        name="Configured Variant",
        ondelete="cascade",
    )

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        domain=[("config_ok", "=", True)],
        string="Configurable Template",
        required=True,
    )

    value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        relation="product_config_session_attr_values_rel",
        column1="cfg_session_id",
        column2="attr_val_id",
    )

    user_id = fields.Many2one(
        comodel_name="res.users", required=True, string="User", tracking=True
    )

    active = fields.Boolean(default=True)

    parent_id = fields.Many2one(
        comodel_name="product.config.session",
        string="Forked From",
        ondelete="set null",
        index=True,
        tracking=True,
        help="Session this one was forked from when another identity took it over",
    )

    access_token = fields.Char(
        string="Resume Token",
        copy=False,
        index=True,
        help="Unguessable token a visitor uses to come back to this "
        "configuration. Never the session number.",
    )

    custom_value_ids = fields.One2many(
        comodel_name="product.config.session.custom.value",
        inverse_name="cfg_session_id",
        string="Custom Values",
    )

    # ⚠️ NON STOCKÉ, et c'est D-092 qui l'impose : « le prix se recalcule à
    # chaque ouverture, pour celui qui regarde ». Un prix stocké serait celui du
    # DERNIER qui a calculé — un particulier transmet au professionnel, et le
    # professionnel lirait le prix du particulier.
    price = fields.Float(
        compute="_compute_cfg_price",
        digits="Product Price",
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        compute="_compute_currency_id",
    )

    state = fields.Selection(
        required=True,
        selection=[("draft", "Draft"), ("done", "Done")],
        default="draft",
        tracking=True,
    )

    weight = fields.Float(compute="_compute_cfg_weight", digits="Stock Weight")
