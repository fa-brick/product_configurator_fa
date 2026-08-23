import logging
import secrets
from ast import literal_eval
from collections.abc import Iterable
from datetime import timedelta
from itertools import chain

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)


class ProductConfigDomain(models.Model):
    _name = "product.config.domain"
    _description = "Domain for Config Restrictions"

    @api.depends("implied_ids")
    def _get_trans_implied(self):
        """Computes the transitive closure of relation implied_ids"""

        def linearize(domains):
            trans_domains = domains
            for domain in domains:
                implied_domains = domain.implied_ids - domain
                if implied_domains:
                    trans_domains |= linearize(implied_domains)
            return trans_domains

        for domain in self:
            domain.trans_implied_ids = linearize(domain)

    def compute_domain(self):
        """Returns a list of domains defined on a
        product.config.domain_line_ids and all implied_ids"""
        # TODO: Enable the usage of OR operators between implied_ids
        # TODO: Add implied_ids sequence field to enforce order of operations
        # TODO: Prevent circular dependencies
        computed_domain = []
        for domain in self:
            lines = domain.trans_implied_ids.mapped("domain_line_ids").sorted()
            if not lines:
                continue
            for line in lines[:-1]:
                if line.operator == "or":
                    computed_domain.append("|")
                computed_domain.append(
                    (line.attribute_id.id, line.condition, line.value_ids.ids)
                )
            # ensure 2 operands follow the last operator
            computed_domain.append(
                (
                    lines[-1].attribute_id.id,
                    lines[-1].condition,
                    lines[-1].value_ids.ids,
                )
            )
        return computed_domain

    ATTRIBUTE_FIELD_PREFIX = "__attribute_"

    @api.model
    def _attribute_field_name(self, attribute):
        """Le nom du champ FICTIF qui représente un attribut dans l'éditeur.

        Même préfixe que les champs dynamiques d'OCA (`__attribute_<id>`) :
        deux conventions pour la même chose finiraient par diverger.
        """
        return f"{self.ATTRIBUTE_FIELD_PREFIX}{attribute.id}"

    def to_odoo_domain(self):
        """Rend la condition sous la forme que le `DomainSelector` sait lire.

        Le stockage reste celui d'OCA — des ENREGISTREMENTS, jamais du texte
        (D-080). Cette traduction ne vit que le temps d'un aller-retour vers
        l'éditeur.
        """
        self.ensure_one()
        domain = []
        lines = self.domain_line_ids.sorted()
        # ⚠️ Même forme que `compute_domain`, y compris sa bizarrerie : le
        # marqueur « | » précède la ligne QUI LE PORTE, et la DERNIÈRE ligne
        # n'en émet jamais (sinon l'opérateur manquerait d'un opérande). Deux
        # rendus qui divergeraient d'un caractère donneraient deux conditions
        # différentes pour un même enregistrement.
        for line in lines[:-1]:
            if line.operator == "or":
                domain.append("|")
            domain.append(
                (
                    self._attribute_field_name(line.attribute_id),
                    line.condition,
                    line.value_ids.ids,
                )
            )
        if lines:
            last = lines[-1]
            domain.append(
                (
                    self._attribute_field_name(last.attribute_id),
                    last.condition,
                    last.value_ids.ids,
                )
            )
        return domain

    def from_odoo_domain(self, domain):
        """Réécrit les lignes de la condition depuis un domaine d'éditeur.

        ⚠️ REFUSE ce que le stockage perdrait. Le `DomainSelector` sait
        exprimer bien plus que les lignes d'OCA ne savent garder — groupes
        imbriqués, autres opérateurs, autres champs. Branché tel quel, il
        laisserait construire une condition que l'enregistrement perdrait EN
        SILENCE (D-080). L'éditeur est restreint en amont ; ce refus est la
        seconde barrière, celle qui ne dépend pas de l'interface.
        """
        self.ensure_one()
        lines = []
        pending_or = False
        for leaf in domain:
            if leaf in ("&", "!"):
                raise ValidationError(
                    self.env._(
                        "Only OR and implicit AND are supported in a "
                        "configuration condition"
                    )
                )
            if leaf == "|":
                pending_or = True
                continue
            field_name, operator, values = leaf
            if not str(field_name).startswith(self.ATTRIBUTE_FIELD_PREFIX):
                raise ValidationError(
                    self.env._(
                        "A configuration condition can only test attributes, "
                        "not '%(field)s'",
                        field=field_name,
                    )
                )
            if operator not in ("in", "not in"):
                raise ValidationError(
                    self.env._(
                        "A configuration condition only supports 'in' and "
                        "'not in', not '%(operator)s'",
                        operator=operator,
                    )
                )
            attribute_id = int(field_name[len(self.ATTRIBUTE_FIELD_PREFIX) :])
            lines.append(
                (
                    0,
                    0,
                    {
                        "attribute_id": attribute_id,
                        "condition": operator,
                        "operator": "or" if pending_or else "and",
                        "value_ids": [(6, 0, list(values))],
                    },
                )
            )
            pending_or = False
        self.domain_line_ids = [(5, 0, 0)] + lines
        return True

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
        compute=_get_trans_implied,
        column1="domain_id",
        column2="parent_id",
        string="Transitively inherits",
    )


class ProductConfigDomainLine(models.Model):
    _name = "product.config.domain.line"
    _order = "sequence"
    _description = "Domain Line for Config Restrictions"

    def _get_domain_conditions(self):
        operators = [("in", "In"), ("not in", "Not In")]

        return operators

    def _get_domain_operators(self):
        andor = [("and", "And"), ("or", "Or")]

        return andor

    @api.depends("attribute_id")
    def _compute_template_attribute_value_ids(self):
        for domain in self:
            domain.template_attribute_value_ids = (
                domain._get_allowed_attribute_value_ids()
            )

    def _compute_attribute_id_domain(self):
        if "product_attribute_ids" in self.env.context:
            return [("id", "in", self.env.context["product_attribute_ids"][0][2])]
        return []

    def _get_allowed_attribute_value_ids(self):
        self.ensure_one()
        product_template = self.env["product.template"]
        if self.env.context.get("product_tmpl_id"):
            product_template = product_template.browse(
                self.env.context.get("product_tmpl_id")
            )
        template_lines = product_template.attribute_line_ids
        attribute_values = self.attribute_id._configurator_value_ids()
        return (
            product_template
            and (template_lines._configurator_value_ids() & attribute_values)
            or attribute_values
        )

    template_attribute_value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        string="Template Attribute Values",
        compute="_compute_template_attribute_value_ids",
    )
    attribute_id = fields.Many2one(
        comodel_name="product.attribute",
        string="Attribute",
        required=True,
        domain=lambda self: self._compute_attribute_id_domain(),
    )
    domain_id = fields.Many2one(
        comodel_name="product.config.domain", required=True, string="Rule"
    )
    condition = fields.Selection(selection=_get_domain_conditions, required=True)
    value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        relation="product_config_domain_line_attr_rel",
        column1="line_id",
        column2="attribute_id",
        string="Values",
        required=True,
    )
    operator = fields.Selection(
        selection=_get_domain_operators,
        string="Operators",
        default="and",
        required=True,
    )
    sequence = fields.Integer(
        default=1,
        help="Set the order of operations for evaluation domain lines",
    )


class ProductConfigLine(models.Model):
    _name = "product.config.line"
    _description = "Product Config Restrictions"
    _order = "product_tmpl_id, sequence, id"

    # TODO: Prevent config lines having dependencies that are not set in other
    # config lines
    # TODO: Prevent circular depdencies: Length -> Color, Color -> Length

    @api.onchange("attribute_line_id")
    def onchange_attribute(self):
        self.value_ids = False
        self.domain_id = False

    @api.depends(
        "product_tmpl_id",
        "attribute_line_id",
        "product_tmpl_id.attribute_line_ids",
        "product_tmpl_id.config_line_ids",
    )
    def _compute_template_attribute_ids(self):
        for config_line in self:
            product_template = config_line.product_tmpl_id
            attribute_line_ids = product_template.attribute_line_ids
            config_line.template_attribute_ids = attribute_line_ids.mapped(
                "attribute_id"
            )

    template_attribute_ids = fields.Many2many(
        comodel_name="product.attribute",
        string="Template Attributes",
        compute="_compute_template_attribute_ids",
    )
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product Template",
        ondelete="cascade",
        required=True,
    )
    attribute_line_id = fields.Many2one(
        comodel_name="product.template.attribute.line",
        string="Attribute Line",
        ondelete="cascade",
        required=True,
    )
    attr_line_val_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        compute="_compute_attr_line_val_ids",
        string="Allowed Attribute Values",
        help="For normal attributes "
        "the values configured for the product can be selected.\n"
        "For custom attributes the 'Custom' value can also be selected.",
    )
    value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        relation="cfg_line_attr_val_id_rel",
        column1="cfg_line_id",
        column2="attr_val_id",
        string="Values",
    )
    domain_id = fields.Many2one(
        comodel_name="product.config.domain",
        required=True,
        string="Restrictions",
    )
    sequence = fields.Integer(default=10)

    @api.constrains("value_ids")
    def check_value_attributes(self):
        """Values selected in config lines must be allowed."""
        for line in self:
            forbidden_values = line.value_ids - line.attr_line_val_ids
            if forbidden_values:
                raise ValidationError(
                    self.env._(
                        "Values must belong to the attribute of the "
                        "corresponding attribute_line set on the "
                        "configuration line"
                    )
                )

    @api.depends(
        "attribute_line_id.value_ids",
        "attribute_line_id.attribute_id.val_custom",
    )
    def _compute_attr_line_val_ids(self):
        for config_line in self:
            config_line.attr_line_val_ids = (
                config_line.attribute_line_id._configurator_value_ids()
            )


class ProductConfigImage(models.Model):
    _name = "product.config.image"
    _inherit = ["image.mixin"]
    _description = "Product Config Image"
    _order = "sequence"

    name = fields.Char(required=True, translate=True)
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product",
        ondelete="cascade",
        required=True,
    )
    sequence = fields.Integer(default=10)
    value_ids = fields.Many2many(
        comodel_name="product.attribute.value", string="Configuration"
    )

    @api.constrains("value_ids")
    def _check_value_ids(self):
        """Check combination of values is possible according to given
        restrictions on linked product template"""
        cfg_session_obj = self.env["product.config.session"]
        for cfg_img in self:
            try:
                cfg_session_obj.validate_configuration(
                    value_ids=cfg_img.value_ids.ids,
                    product_tmpl_id=cfg_img.product_tmpl_id.id,
                    final=False,
                )
            except ValidationError as exc:
                raise ValidationError(
                    self.env._(
                        "Values entered for line '%s' generate "
                        "a incompatible configuration",
                        cfg_img.name,
                    )
                ) from exc


class ProductConfigStep(models.Model):
    _name = "product.config.step"
    _description = "Product Config Steps"

    # TODO: Prevent values which have dependencies to be set in a
    #       step with higher sequence than the dependency

    name = fields.Char(required=True, translate=True)


class ProductConfigStepLine(models.Model):
    _name = "product.config.step.line"
    _description = "Product Config Step Lines"
    _order = "sequence, config_step_id, id"

    name = fields.Char(related="config_step_id.name")
    config_step_id = fields.Many2one(
        comodel_name="product.config.step",
        string="Configuration Step",
        required=True,
    )
    attribute_line_ids = fields.Many2many(
        comodel_name="product.template.attribute.line",
        relation="config_step_line_attr_id_rel",
        column1="cfg_line_id",
        column2="attr_id",
        string="Attribute Lines",
    )
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product Template",
        ondelete="cascade",
        required=True,
    )
    sequence = fields.Integer(default=10)
    visibility_domain_id = fields.Many2one(
        comodel_name="product.config.domain",
        string="Visibility Condition",
        ondelete="restrict",
        help="This step is shown only when the condition matches. "
        "Empty means always shown.",
    )

    def _is_visible(self, value_ids=None, custom_vals=None):
        """L'étape est-elle montrée pour cette configuration ? — D-086.

        Sans condition, oui : une étape ne se cache pas par défaut.
        """
        self.ensure_one()
        if not self.visibility_domain_id:
            return True
        session = self.env["product.config.session"]
        return session.validate_domains_against_sels(
            self.visibility_domain_id.compute_domain(),
            value_ids or [],
            custom_vals or {},
        )

    @api.constrains("config_step_id")
    def _check_config_step(self):
        """Prevent to add same step more than once on same product template"""
        for config_step in self:
            cfg_step_lines = config_step.product_tmpl_id.config_step_line_ids
            cfg_steps = cfg_step_lines.filtered(
                lambda line, config_step=config_step: line != config_step
            ).mapped("config_step_id")
            if config_step.config_step_id in cfg_steps:
                raise ValidationError(
                    self.env._("Cannot have a configuration step defined twice.")
                )


class ProductConfigSession(models.Model):
    # ⚠️ `mail.thread` : une session passe de main en main — un particulier, un
    # professionnel, un commercial. Savoir qui a changé quoi et quand n'est pas
    # un luxe (D-092). OCA n'en avait aucune trace.
    _name = "product.config.session"
    _inherit = ["mail.thread"]
    _description = "Product Config Session"

    @api.depends(
        "value_ids",
        "product_tmpl_id.list_price",
        "product_tmpl_id.attribute_line_ids",
        "product_tmpl_id.attribute_line_ids.value_ids",
        "product_tmpl_id.attribute_line_ids.product_template_value_ids",
        "product_tmpl_id.attribute_line_ids." "product_template_value_ids.price_extra",
    )
    def _compute_cfg_price(self):
        for session in self:
            if session.product_tmpl_id:
                price = session.get_cfg_price()
            else:
                price = 0.00
            session.price = price

    def get_custom_value_id(self):
        """Return record set of attribute value 'custom'"""
        custom_ext_id = "product_configurator_fa.custom_attribute_value"
        custom_val_id = self.env.ref(custom_ext_id)
        return custom_val_id

    @api.model
    def _get_custom_vals_dict(self):
        """Retrieve session custom values as a dictionary of the form
        {attribute_id: parsed_custom_value}"""
        custom_vals = {}
        for val in self.custom_value_ids:
            if val.attribute_id.custom_type in ["float", "integer"]:
                custom_vals[val.attribute_id.id] = literal_eval(val.value)
            elif val.attribute_id.custom_type == "binary":
                custom_vals[val.attribute_id.id] = val.attachment_ids
            else:
                custom_vals[val.attribute_id.id] = val.value
        return custom_vals

    def _compute_config_step_name(self):
        """Get the config.step.line name using the string stored in config_step
        field of the session"""
        cfg_step_line_obj = self.env["product.config.step.line"]
        cfg_session_step_lines = self.mapped("config_step")
        cfg_step_line_ids = set()
        for step in cfg_session_step_lines:
            try:
                cfg_step_line_ids.add(int(step))
            except ValueError:
                _logger.debug("Step from session not valid")
        cfg_step_lines = cfg_step_line_obj.browse(cfg_step_line_ids)
        for session in self:
            try:
                config_step = int(session.config_step)
                config_step_line = cfg_step_lines.filtered(
                    lambda x, config_step=config_step: x.id == config_step
                )
                session.config_step_name = config_step_line.name
            except Exception:
                _logger.debug("Invalid session data ignored")
            if not session.config_step_name:
                session.config_step_name = session.config_step

    def flatten_attribute_value_ids(self, value_ids):
        return chain.from_iterable(
            v if isinstance(v, Iterable) else [v] for v in value_ids
        )

    @api.model
    def get_cfg_weight(self, value_ids=None, custom_vals=None):
        """Computes the weight of the configured product based on the
        configuration passed in via value_ids and custom_values

        :param value_ids: list of attribute value_ids
        :param custom_vals: dictionary of custom attribute values
        :returns: final configuration weight"""

        if value_ids is None:
            value_ids = self.value_ids.ids

        if custom_vals is None:
            custom_vals = {}

        product_tmpl = self.product_tmpl_id

        self = self.with_context(active_id=product_tmpl.id)

        value_ids = list(self.flatten_attribute_value_ids(value_ids))

        weight_extra = 0.0
        product_attr_val_obj = self.env["product.template.attribute.value"]
        product_tmpl_attr_values = product_attr_val_obj.search(
            [
                ("product_tmpl_id", "in", product_tmpl.ids),
                ("product_attribute_value_id", "in", value_ids),
            ]
        )
        for product_tmpl_attr_val in product_tmpl_attr_values:
            weight_extra += product_tmpl_attr_val.weight_extra

        return product_tmpl.weight + weight_extra

    @api.depends(
        "value_ids",
        "product_tmpl_id",
        "product_tmpl_id.attribute_line_ids",
        "product_tmpl_id.attribute_line_ids.value_ids",
        "product_tmpl_id.attribute_line_ids.product_template_value_ids",
        "product_tmpl_id.attribute_line_ids.product_template_value_ids" ".weight_extra",
    )
    def _compute_cfg_weight(self):
        for cfg_session in self:
            cfg_session.weight = cfg_session.get_cfg_weight()

    def _compute_currency_id(self):
        main_company = self.env["res.company"]._get_main_company()
        for session in self:
            template = session.product_tmpl_id
            session.currency_id = (
                template.company_id.sudo().currency_id.id or main_company.currency_id.id
            )

    name = fields.Char(string="Configuration Session Number", readonly=True)
    config_step = fields.Char(string="Configuration Step ID")
    config_step_name = fields.Char(
        compute="_compute_config_step_name", string="Configuration Step"
    )
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
    child_ids = fields.One2many(
        comodel_name="product.config.session",
        inverse_name="parent_id",
        string="Forks",
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
    # Product preset
    product_preset_id = fields.Many2one(
        comodel_name="product.product",
        string="Preset",
    )

    @api.model
    def _session_validity_days(self):
        """Combien de jours un lien de reprise reste valable.

        ⚠️ **Le même paramètre gouverne le ménage** : nettoyer une session plus
        tôt que la promesse faite au visiteur (« ce lien reste valable N jours »)
        serait un défaut visible du client (D-091, D-082).
        """
        return int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("product_configurator_fa.session_gc_days", 90)
        )

    def _ensure_access_token(self):
        """Pose un jeton ALÉATOIRE, distinct du numéro de session — D-091.

        ⚠️ `name` vaut `CS0001`, `CS0002`… : une séquence énumérable. Le donner
        au visiteur laisserait lire les configurations des autres en tapant
        `CS0042` — produit, dimensions, prix, et le client dès que la
        configuration devient un devis. Ce n'est pas un risque théorique.

        Et le contrôle d'accès ne peut pas venir d'ailleurs : un visiteur
        anonyme est l'utilisateur PUBLIC, donc toutes les sessions anonymes
        appartiendraient au même `user_id`. **Le jeton EST l'identité**, ce qui
        rend son imprévisibilité non négociable.
        """
        for session in self:
            if not session.sudo().access_token:
                session.sudo().access_token = secrets.token_urlsafe(32)
        return True

    @api.model
    def _find_by_access_token(self, token):
        """Retrouve une session par son jeton, ou rien — jamais par son numéro."""
        if not token or not isinstance(token, str):
            return self.browse()
        session = (
            self.sudo()
            .with_context(active_test=False)
            .search([("access_token", "=", token)], limit=1)
        )
        if not session:
            return self.browse()
        limit = fields.Datetime.now() - timedelta(days=self._session_validity_days())
        if session.create_date < limit or not session.active:
            # La promesse faite au visiteur est datée : passé l'échéance, le
            # lien ne rend rien plutôt que d'ouvrir une configuration qu'on a
            # pu nettoyer entre-temps.
            return self.browse()
        return session

    def _session_for_edit(self):
        """Rend la session dans laquelle ÉCRIRE — la mienne, ou une fourche.

        Une session appartient à une IDENTITÉ (D-092) : quand un utilisateur
        identifié reprend celle d'un autre, une nouvelle session naît, reliée à
        l'originale, et l'original garde sa version intacte.

        ⚠️ La fourche a lieu à la première MODIFICATION, pas à l'ouverture —
        sinon le commercial qui vient seulement regarder crée une session pour
        rien. C'est la doctrine de D-082 appliquée ici.
        """
        self.ensure_one()
        user = self.env.user
        if self.user_id == user:
            return self
        fork = self.copy(
            {
                "user_id": user.id,
                "parent_id": self.id,
                "state": "draft",
                "product_id": False,
                "access_token": False,
            }
        )
        fork._ensure_access_token()
        fork._message_log(
            body=self.env._(
                "Configuration taken over from %(session)s", session=self.display_name
            )
        )
        return fork

    @api.autovacuum
    def _gc_config_sessions(self):
        """Archive les sessions abandonnées — D-082.

        ⚠️ Le crochet se prend par le DÉCORATEUR en Odoo 18, pas par le nom
        ([[L-137]]). Et le critère n'est pas seulement l'âge : une session
        confirmée, ou qui a donné une variante, a servi — on n'y touche pas.
        """
        limit = fields.Datetime.now() - timedelta(days=self._session_validity_days())
        abandoned = self.sudo().search(
            [
                ("state", "=", "draft"),
                ("product_id", "=", False),
                ("create_date", "<", limit),
            ]
        )
        abandoned.write({"active": False})

    def action_confirm(self, product_id=None):
        for session in self:
            if product_id is None:
                product_id = session.create_get_variant()
            session.write({"state": "done", "product_id": product_id.id})
        return True

    @api.constrains("state")
    def _check_product_id(self):
        for session in self.filtered(lambda s: s.state == "done"):
            if not session.product_id:
                raise ValidationError(
                    self.env._(
                        "Finished configuration session must have a "
                        "product_id linked"
                    )
                )

    def update_session_configuration_value(self, vals, product_tmpl_id=None):
        """Update value of configuration in current session

        :param: vals: Dictionary of fields(of configution wizard) and values
        :param: product_tmpl_id: record set of preoduct template
        :return: True/False
        """
        self.ensure_one()
        if not product_tmpl_id:
            product_tmpl_id = self.product_tmpl_id

        product_configurator_fa_obj = self.env["product.configurator"]
        field_prefix = product_configurator_fa_obj._prefixes.get("field_prefix")
        custom_field_prefix = product_configurator_fa_obj._prefixes.get(
            "custom_field_prefix"
        )

        custom_val = self.get_custom_value_id()
        attr_val_dict = {}
        custom_val_dict = {}

        for attr_line in product_tmpl_id.attribute_line_ids:
            attr_id = attr_line.attribute_id.id
            field_name = field_prefix + str(attr_id)
            custom_field_name = custom_field_prefix + str(attr_id)

            if field_name not in vals and custom_field_name not in vals:
                continue

            # Add attribute values from the client except custom attribute
            # If a custom value is being written, but field name is not in
            # the write dictionary, then it must be a custom value!
            if vals.get(field_name, custom_val.id) != custom_val.id:
                if attr_line.multi and isinstance(vals[field_name], list):
                    field_val = self._update_field_values(vals, field_name, attr_line)
                elif not attr_line.multi and isinstance(vals[field_name], int):
                    field_val = vals[field_name]
                else:
                    raise UserError(
                        self.env._(
                            "An error occurred while parsing value for attribute %s",
                            attr_line.attribute_id.name,
                        )
                    )
                attr_val_dict.update({attr_id: field_val})
                # Ensure there is no custom value stored if we have switched
                # from custom value to selected attribute value.
                if attr_line.custom:
                    custom_val_dict.update({attr_id: False})
            elif attr_line.custom:
                val = vals.get(custom_field_name, False)
                if attr_line.attribute_id.custom_type == "binary":
                    # TODO: Add widget that enables multiple file uploads
                    val = [{"name": "custom", "datas": vals[custom_field_name]}]
                custom_val_dict.update({attr_id: val})
                # Ensure there is no standard value stored if we have switched
                # from selected value to custom value.
                attr_val_dict.update({attr_id: custom_val.id})

        self.update_config(attr_val_dict, custom_val_dict)

    def _update_field_values(self, vals, field_name, attr_line):
        """New method for update field values for a given attribute."""
        final_val = None
        if not vals[field_name]:
            return final_val
        # Retrieve existing values for the attribute
        value_ids = self.value_ids.filtered(
            lambda value, attr_line=attr_line: value.attribute_id.id
            == attr_line.attribute_id.id
        )
        # Initialize `final_val` with IDs
        final_val = value_ids.ids or []

        # Process each `field_vals` operation for the current attribute
        for field_vals in vals.get(field_name, []):
            if field_vals and field_vals[0] == Command.SET:
                final_val = list(set(field_vals[2] or []))
            elif field_vals and field_vals[0] == Command.LINK:
                if field_vals[1] not in final_val:
                    final_val.append(field_vals[1])
            elif field_vals and field_vals[0] in (Command.UNLINK, Command.DELETE):
                if field_vals[1] in final_val:
                    final_val.remove(field_vals[1])

        return final_val

    def update_config(self, attr_val_dict=None, custom_val_dict=None):
        """Update the session object with the given value_ids and custom values.

        Use this method instead of write in order to prevent incompatible
        configurations as this removed duplicate values for the same attribute.

        :param attr_val_dict: Dictionary of the form {
            int (attribute_id): attribute_value_id OR [attribute_value_ids]
        }

        :custom_val_dict: Dictionary of the form {
            int (attribute_id): {
                'value': 'custom val',
                OR
                'attachment_ids': {
                    [{
                        'name': 'attachment name',
                        'datas': base64_encoded_string
                    }]
                }
            }
        }

        """
        if attr_val_dict is None:
            attr_val_dict = {}
        if custom_val_dict is None:
            custom_val_dict = {}
        update_vals = {}

        value_ids = self.value_ids.ids
        for attr_id, vals in attr_val_dict.items():
            attr_val_ids = self.value_ids.filtered(
                lambda x, attr_id=attr_id: x.attribute_id.id == int(attr_id)
            ).ids
            # Remove all values for this attribute and add vals from dict
            value_ids = list(set(value_ids) - set(attr_val_ids))
            if not vals:
                continue
            if isinstance(vals, list):
                value_ids += vals
            elif isinstance(vals, int):
                value_ids.append(vals)

        if value_ids != self.value_ids.ids:
            update_vals.update({"value_ids": [(6, 0, value_ids)]})

        # Remove all custom values included in the custom_vals dict
        self.custom_value_ids.filtered(
            lambda x: x.attribute_id.id in custom_val_dict.keys()
        ).unlink()

        if custom_val_dict:
            binary_field_ids = (
                self.env["product.attribute"]
                .search(
                    [
                        ("id", "in", list(custom_val_dict.keys())),
                        ("custom_type", "=", "binary"),
                    ]
                )
                .ids
            )
        else:
            binary_field_ids = []

        for attr_id, vals in custom_val_dict.items():
            if not vals:
                continue

            if "custom_value_ids" not in update_vals:
                update_vals["custom_value_ids"] = []

            custom_vals = {"attribute_id": attr_id}

            if attr_id in binary_field_ids:
                attachments = [
                    (
                        0,
                        0,
                        {"name": val.get("name"), "datas": val.get("datas")},
                    )
                    for val in vals
                ]
                custom_vals.update({"attachment_ids": attachments})
            else:
                custom_vals.update({"value": vals})

            update_vals["custom_value_ids"].append((0, 0, custom_vals))
        self.write(update_vals)

    def write(self, vals):
        """Validate configuration when writing new values to session"""
        # TODO: Issue warning when writing to value_ids or custom_val_ids
        res = super().write(vals)
        if not self.product_tmpl_id:
            return res
        value_ids = self.value_ids.ids
        avail_val_ids = self.values_available(value_ids)
        if set(value_ids) - set(avail_val_ids):
            self.value_ids = [(6, 0, avail_val_ids)]
        try:
            self.validate_configuration(final=False)
        except ValidationError as exc:
            raise ValidationError(self.env._(f"{exc}")) from exc
        except Exception as exc:
            raise ValidationError(self.env._("Invalid Configuration")) from exc
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "product.config.session"
            ) or self.env._("New")
            product_tmpl = (
                self.env["product.template"]
                .browse(vals.get("product_tmpl_id"))
                .exists()
            )
            if product_tmpl:
                default_val_ids = (
                    product_tmpl.attribute_line_ids.filtered(
                        lambda line: line.default_val
                    )
                    .mapped("default_val")
                    .ids
                )
                value_ids = vals.get("value_ids")
                if value_ids:
                    default_val_ids += value_ids[0][2]
                try:
                    self.validate_configuration(
                        value_ids=default_val_ids,
                        final=False,
                        product_tmpl_id=product_tmpl.id,
                    )
                    # TODO: Remove if cond when PR with
                    # raise error on github is merged
                except ValidationError as exc:
                    raise ValidationError(self.env._("%s") % exc.name) from exc
                except Exception as exc:
                    raise ValidationError(
                        self.env._(
                            "Default values provided generate an invalid "
                            "configuration"
                        )
                    ) from exc
                vals.update({"value_ids": [(6, 0, default_val_ids)]})
        sessions = super().create(vals_list)
        # ⚠️ Le jeton se pose ICI et non dans un second `create` : la classe en
        # définit déjà un, et une seconde définition du même nom écraserait la
        # première EN SILENCE — c'est Python, pas Odoo, qui tranche ([[L-141]]).
        sessions._ensure_access_token()
        return sessions

    def create_get_variant(self, value_ids=None, custom_vals=None):
        """Creates a new product variant with the attributes passed
        via value_ids and custom_values or retrieves an existing
        one based on search result

            :param value_ids: list of product.attribute.values ids
            :param custom_vals: dict {product.attribute.id: custom_value}

            :returns: new/existing product.product recordset

        """
        if self.product_tmpl_id.config_ok:
            self.validate_configuration()
        if value_ids is None:
            value_ids = self.value_ids.ids

        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()

        try:
            self.validate_configuration()
        except ValidationError as exc:
            raise ValidationError(self.env._("%s") % exc.name) from exc
        except Exception as exc:
            raise ValidationError(self.env._("Invalid Configuration")) from exc

        # La saisie libre devient une VALEUR d'attribut ici, et pas avant :
        # une configuration abandonnée ne doit rien laisser derrière elle
        # (D-082). C'est ce qui rend la variante distinguable en stock (D-081).
        value_ids = self._resolve_numeric_custom_vals(value_ids, custom_vals)

        duplicates = self.search_variant(
            value_ids=value_ids, product_tmpl_id=self.product_tmpl_id
        )
        if duplicates:
            return duplicates[:1]

        vals = self.get_variant_vals(value_ids, custom_vals)
        product_obj = (
            self.env["product.product"].sudo().with_context(mail_create_nolog=True)
        )
        variant = product_obj.sudo().create(vals)

        variant.message_post(
            body=self.env._("Product created via configuration wizard"),
            author_id=self.env.user.partner_id.id,
        )

        return variant

    def _resolve_numeric_custom_vals(self, value_ids, custom_vals):
        """Range les saisies numériques en valeurs d'attribut — D-081.

        Rend les `value_ids` augmentés. La session, elle, n'est PAS modifiée :
        elle garde le nombre en clair, qui est la trace de ce que le client a
        tapé, et le seul enregistrement neuf est celui qu'exige la variante.
        """
        self.ensure_one()
        resolved = list(value_ids or [])
        for line in self.product_tmpl_id.attribute_line_ids:
            attribute = line.attribute_id
            if attribute.id not in (custom_vals or {}):
                continue
            if not attribute._resolves_to_values():
                continue
            value = line.resolve_numeric_value(custom_vals[attribute.id])
            if value and value.id not in resolved:
                resolved.append(value.id)
        return resolved

    def _get_option_values(self, pricelist, value_ids=None):
        """Return only attribute values that have products attached with a
        price set to them"""
        if value_ids is None:
            value_ids = self.value_ids.ids

        value_obj = self.env["product.attribute.value"].with_context(
            pricelist=pricelist.id
        )
        values = (
            value_obj.sudo()
            .browse(value_ids)
            .filtered(lambda x: x.product_id._get_contextual_price())
        )
        return values

    def get_components_prices(self, prices, pricelist, value_ids=None):
        """Return prices of the components which make up the final
        configured variant"""
        if value_ids is None:
            value_ids = self.value_ids.ids
        vals = self._get_option_values(pricelist, value_ids)
        for val in vals:
            prices["vals"].append(
                (
                    val.attribute_id.name,
                    val.product_id.name,
                    val.product_id._get_contextual_price(),
                )
            )
            product = val.product_id.with_context(pricelist=pricelist.id)
            product_prices = product.taxes_id.sudo().compute_all(
                price_unit=product._get_contextual_price(),
                currency=pricelist.currency_id,
                quantity=1,
                product=self,
                partner=self.env.user.partner_id,
            )

            total_included = product_prices["total_included"]
            taxes = total_included - product_prices["total_excluded"]
            prices["taxes"] += taxes
            prices["total"] += total_included
        return prices

    @api.model
    def get_cfg_price(self, value_ids=None, custom_vals=None, pricelist=None):
        """Computes the price of the configured product based on the
            configuration passed in via value_ids and custom_values

        :param value_ids: list of attribute value_ids
        :param custom_vals: dictionary of custom attribute values
        :returns: final configuration price"""

        if value_ids is None:
            value_ids = self.value_ids.ids

        if custom_vals is None:
            custom_vals = {}

        product_tmpl = self.product_tmpl_id
        self = self.with_context(active_id=product_tmpl.id)

        value_ids = self.flatten_val_ids(value_ids)

        price_extra = 0.0
        attr_val_obj = self.env["product.attribute.value"]
        av_ids = attr_val_obj.browse(value_ids)
        extra_prices = attr_val_obj.get_attribute_value_extra_prices(
            product_tmpl_id=product_tmpl.id, pt_attr_value_ids=av_ids
        )
        price_extra = sum(extra_prices.values())
        # Le prix d'un produit DIMENSIONNÉ vient de sa grille, pas du
        # `list_price` du template — lequel n'est qu'un « à partir de » (D-083,
        # D-093). Faute de grille, on retombe sur le comportement d'OCA : le
        # produit n'est pas dimensionné, ou son absence de grille a déjà été
        # signalée à l'arrivée dans la fiche.
        base_price = self._get_config_grid_price(value_ids, custom_vals)
        if base_price is None:
            base_price = product_tmpl.list_price
        price_sqm = self._get_cfg_price_sqm(value_ids, custom_vals)

        # ⚠️ OCA rendait `list_price + price_extra`, SANS liste de prix — alors
        # que les options, elles, en tenaient compte (`_get_option_values`).
        # Pour le flux particulier → professionnel, c'était bloquant : les deux
        # voyaient le même prix (D-092).
        #
        # Le passage par la liste de prix n'est pas un calcul de plus : c'est le
        # MÊME chemin que celui d'un devis — pourcentages, formules, devise,
        # arrondis, cascades. Le prix de base y entre par le contexte, faute de
        # variante : rien n'est créé avant le devis (D-082).
        if pricelist is None:
            pricelist = self.env.user.partner_id.property_product_pricelist
        if not pricelist:
            return base_price + price_extra + price_sqm
        template = product_tmpl.with_context(
            configurator_base_prices={product_tmpl.id: base_price},
            current_attributes_price_extra=[price_extra, price_sqm],
        )
        return pricelist._get_product_price(template, 1.0)

    def _get_config_dimensions(self, value_ids=None, custom_vals=None):
        """Les deux cotes de la configuration COURANTE — D-098, D-161.

        Pendant la configuration, une cote peut être encore une saisie libre
        (`custom_vals`) ou déjà une valeur retenue (`value_ids`) : les deux
        chemins existent, parce que le rangement en valeur n'a lieu qu'au devis
        (D-082). On lit donc la saisie d'abord, la valeur ensuite.
        """
        self.ensure_one()
        if custom_vals is None:
            custom_vals = {}
        dimensions = {}
        for role, line in self.product_tmpl_id._grid_axis_lines().items():
            attribute = line.attribute_id
            raw = custom_vals.get(attribute.id)
            if raw in (None, False, ""):
                chosen = attribute.value_ids.filtered(
                    lambda value, ids=value_ids or []: value.id in ids
                )
                raw = chosen[:1].name if chosen else None
            try:
                dimensions[role] = float(raw)
            except (TypeError, ValueError):
                continue
        return dimensions

    def _get_config_grid_price(self, value_ids=None, custom_vals=None):
        """Le prix de grille de la configuration courante, ou `None`."""
        self.ensure_one()
        grid = self.product_tmpl_id._get_price_grid()
        if not grid:
            return None
        dimensions = self._get_config_dimensions(value_ids, custom_vals)
        if "axis_x" not in dimensions or "axis_y" not in dimensions:
            return None
        return grid.get_price(dimensions["axis_x"], dimensions["axis_y"])

    def get_config_surface(self, value_ids=None, custom_vals=None):
        """La surface en m² de la configuration courante, ou 0 — D-161.

        Point d'appel PUBLIC : c'est l'interface qui en a besoin, pour poser
        `configurator_surface` dans le contexte et faire afficher aux valeurs au
        mètre carré leur MONTANT plutôt que leur taux (arbitrage Gerry).

        Rend 0 tant que les deux cotes ne sont pas connues — et zéro veut dire
        « on ne sait pas encore », pas « c'est gratuit » : l'étiquette retombe
        alors sur le taux, qui reste juste.
        """
        self.ensure_one()
        dimensions = self._get_config_dimensions(value_ids, custom_vals)
        if "axis_x" not in dimensions or "axis_y" not in dimensions:
            return 0.0
        return self.product_tmpl_id._grid_surface(
            dimensions["axis_x"], dimensions["axis_y"]
        )

    def _get_cfg_price_sqm(self, value_ids=None, custom_vals=None):
        """La part des suppléments AU MÈTRE CARRÉ — D-162.

        Le taux vit dans `price_extra_sqm`, jamais dans `price_extra` : Odoo
        somme ce dernier partout, et y ranger 25 €/m² le ferait facturer 25 €.
        """
        self.ensure_one()
        dimensions = self._get_config_dimensions(value_ids, custom_vals)
        if "axis_x" not in dimensions or "axis_y" not in dimensions:
            return 0.0
        rated = self.env["product.template.attribute.value"].search(
            [
                ("product_tmpl_id", "=", self.product_tmpl_id.id),
                ("product_attribute_value_id", "in", value_ids or []),
                ("price_extra_sqm", "!=", 0),
            ]
        )
        rated = rated.filtered(
            lambda ptav: ptav.attribute_line_id.price_mode == "per_sqm"
        )
        if not rated:
            return 0.0
        surface = self.product_tmpl_id._grid_surface(
            dimensions["axis_x"], dimensions["axis_y"]
        )
        return sum(rated.mapped("price_extra_sqm")) * surface

    def _get_config_image(self, value_ids=None, custom_vals=None, size=None):
        """
        Retreive the image object that most closely resembles the configuration
        code sent via value_ids list

        The default image object is the template (self)
        :param value_ids: a list representing the ids of attribute values
                         (usually stored in the user's session)
        :param custom_vals: dictionary of custom attribute values
        :returns: path to the selected image
        """
        # TODO: Also consider custom values for image change
        if value_ids is None:
            value_ids = self.value_ids.ids

        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()

        img_obj = self.product_tmpl_id
        max_matches = 0
        value_ids = self.flatten_val_ids(value_ids)
        for line in self.product_tmpl_id.config_image_ids:
            matches = len(set(line.value_ids.ids) & set(value_ids))
            if matches > max_matches:
                img_obj = line
                max_matches = matches
        return img_obj

    def get_config_image(self, value_ids=None, custom_vals=None, size=None):
        """
        Retreive the image object that most closely resembles the configuration
        code sent via value_ids list
        For more information check _get_config_image
        """
        config_image_id = self._get_config_image(
            value_ids=value_ids, custom_vals=custom_vals
        )
        return config_image_id.image_1920

    @api.model
    def get_variant_vals(self, value_ids=None, custom_vals=None, **kwargs):
        """Hook to alter the values of the product variant before creation

        :param value_ids: list of product.attribute.values ids
        :param custom_vals: dict {product.attribute.id: custom_value}

        :returns: dictionary of values to pass to product.create() method
        """
        self.ensure_one()

        if value_ids is None:
            value_ids = self.value_ids.ids

        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()

        image = self.get_config_image(value_ids)
        ptav_ids = self.env["product.template.attribute.value"].search(
            [
                ("product_tmpl_id", "=", self.product_tmpl_id.id),
                ("product_attribute_value_id", "in", value_ids),
            ]
        )
        vals = {
            "product_tmpl_id": self.product_tmpl_id.id,
            "product_template_attribute_value_ids": [(6, 0, ptav_ids.ids)],
            "taxes_id": [(6, 0, self.product_tmpl_id.taxes_id.ids)],
            "image_1920": image,
        }
        return vals

    def get_session_search_domain(self, product_tmpl_id, state="draft", parent_id=None):
        """Return domain to search session linked to given
        product template and current login user"""
        domain = [
            ("product_tmpl_id", "=", product_tmpl_id),
            ("user_id", "=", self.env.uid),
            ("state", "=", state),
        ]
        if parent_id:
            domain.append(("parent_id", "=", parent_id))
        return domain

    def get_session_vals(self, product_tmpl_id, parent_id=None, user_id=None):
        """Return the values for creating session"""
        if not user_id:
            user_id = self.env.user.id
        vals = {"product_tmpl_id": product_tmpl_id, "user_id": user_id}
        if parent_id:
            vals.update(parent_id=parent_id)
        return vals

    def get_next_step(
        self,
        state,
        product_tmpl_id=False,
        value_ids=False,
        custom_value_ids=False,
    ):
        """Find and return next step if it exists. This usually
        implies the next configuration step (if any) defined via the
        config_step_line_ids on the product.template.
        """

        if not product_tmpl_id:
            product_tmpl_id = self.product_tmpl_id
        if value_ids is False:
            value_ids = self.value_ids
        if custom_value_ids is False:
            custom_value_ids = self.custom_value_ids
        if not state:
            state = self.config_step

        cfg_step_lines = product_tmpl_id.config_step_line_ids
        if not cfg_step_lines:
            if (value_ids or custom_value_ids) and state != "select":
                return False
            elif not (value_ids or custom_value_ids) and state != "select":
                raise UserError(
                    self.env._(
                        "You must select at least one "
                        "attribute in order to configure a product"
                    )
                )
            else:
                return "configure"

        adjacent_steps = self.get_adjacent_steps()
        next_step = adjacent_steps.get("next_step")
        open_step_lines = list(map(str, self.get_open_step_lines().ids))

        session_config_step = self.config_step
        if (
            session_config_step
            and state != session_config_step
            and session_config_step in open_step_lines
        ):
            next_step = self.config_step
        else:
            next_step = str(next_step.id) if next_step else None
        if next_step:
            pass
        elif not (value_ids or custom_value_ids):
            raise UserError(
                self.env._(
                    "You must select at least one "
                    "attribute in order to configure a product"
                )
            )
        else:
            return False
        return next_step

    # TODO: Should be renamed to get_active_step_line

    @api.model
    def get_active_step(self):
        """Attempt to return product.config.step.line object that has the id
        of the config session step stored as string"""
        cfg_step_line_obj = self.env["product.config.step.line"]

        try:
            cfg_step_line_id = int(self.config_step)
        except ValueError:
            cfg_step_line_id = None

        if cfg_step_line_id:
            return cfg_step_line_obj.browse(cfg_step_line_id)
        return cfg_step_line_obj

    @api.model
    def get_open_step_lines(self, value_ids=None):
        """
        Returns a recordset of configuration step lines open for access given
        the configuration passed through value_ids

        e.g: Field A and B from configuration step 2 depend on Field C
        from configuration step 1. Since fields A and B require action from
        the previous step, configuration step 2 is deemed closed and redirect
        is made for configuration step 1.

        :param value_ids: list of value.ids representing the
                          current configuration
        :returns: recordset of accesible configuration steps
        """

        if value_ids is None:
            value_ids = self.value_ids.ids

        open_step_lines = self.env["product.config.step.line"]

        for cfg_line in self.product_tmpl_id.config_step_line_ids:
            # ⚠️ La condition EXPLICITE tranche avant l'effet de bord : une
            # étape masquée par sa condition ne s'ouvre pas, même si ses
            # attributs ont des valeurs disponibles (D-086).
            if not cfg_line._is_visible(value_ids):
                continue
            for attr_line in cfg_line.attribute_line_ids:
                available_vals = self.values_available(
                    attr_line.value_ids.ids,
                    value_ids,
                    product_template_attribute_line_id=attr_line.id,
                )
                # TODO: Refactor when adding restriction to custom values
                if available_vals or attr_line.custom:
                    open_step_lines |= cfg_line
                    break

        return open_step_lines.sorted()

    @api.model
    def get_all_step_lines(self, product_tmpl_id=None):
        """
        Returns a recordset of configuration step lines of product_tmpl_id

        :param product_tmpl_id: record-set of product.template
        :returns: recordset of all configuration steps
        """
        if not product_tmpl_id:
            product_tmpl_id = self.product_tmpl_id

        open_step_lines = product_tmpl_id.config_step_line_ids
        return open_step_lines.sorted()

    @api.model
    def get_adjacent_steps(self, value_ids=None, active_step_line_id=None):
        """Returns the previous and next steps given the configuration passed
        via value_ids and the active step line passed via cfg_step_line_id."""

        # If there is no open step return empty dictionary

        if value_ids is None:
            value_ids = self.value_ids.ids

        if not active_step_line_id:
            active_step_line_id = self.get_active_step().id

        config_step_lines = self.product_tmpl_id.config_step_line_ids

        if not config_step_lines:
            return {}

        active_cfg_step_line = config_step_lines.filtered(
            lambda line: line.id == active_step_line_id
        )

        open_step_lines = self.get_open_step_lines(value_ids)

        if not active_cfg_step_line:
            return {"next_step": open_step_lines[0]}

        nr_steps = len(open_step_lines)

        adjacent_steps = {}

        for i, cfg_step in enumerate(open_step_lines):
            if cfg_step == active_cfg_step_line:
                adjacent_steps.update(
                    {
                        "next_step": None
                        if i + 1 == nr_steps
                        else open_step_lines[i + 1],
                        "previous_step": None if i == 0 else open_step_lines[i - 1],
                    }
                )
        return adjacent_steps

    def check_and_open_incomplete_step(self, value_ids=None, custom_value_ids=None):
        """Check and open incomplete step if any
        :param value_ids: recordset of product.attribute.value
        """
        if value_ids is None:
            value_ids = self.value_ids
        if custom_value_ids is None:
            custom_value_ids = self.custom_value_ids
        custom_attr_selected = custom_value_ids.mapped("attribute_id")
        open_step_lines = self.get_open_step_lines()
        step_to_open = False
        for step in open_step_lines:
            unset_attr_line = step.attribute_line_ids.filtered(
                lambda attr_line: attr_line.required
                and not any([value in value_ids for value in attr_line.value_ids])
                and not (
                    attr_line.custom and attr_line.attribute_id in custom_attr_selected
                )
            )
            check_val_ids = unset_attr_line.mapped("value_ids")
            avail_val_ids = self.values_available(
                check_val_ids.ids,
                value_ids.ids,
                product_tmpl_id=self.product_tmpl_id,
            )
            if unset_attr_line and avail_val_ids:
                step_to_open = step
                break
        if step_to_open:
            return str(step_to_open.id)
        return False

    @api.model
    def get_variant_search_domain(self, product_tmpl_id, value_ids=None):
        """Method called by search_variant used to search duplicates in the
        database"""

        if value_ids is None:
            value_ids = self.value_ids.ids

        domain = [
            ("product_tmpl_id", "=", product_tmpl_id.id),
            ("config_ok", "=", True),
        ]
        pta_value_ids = self.env["product.template.attribute.value"].search(
            [
                ("product_tmpl_id", "=", product_tmpl_id.id),
                ("product_attribute_value_id", "in", value_ids),
            ]
        )
        for value_id in pta_value_ids:
            domain.append(("product_template_attribute_value_ids", "=", value_id.id))
        return domain

    def validate_domains_against_sels(self, domains, value_ids=None, custom_vals=None):
        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()

        if value_ids is None:
            value_ids = self.value_ids.ids

        # process domains as shown in this wikipedia pseudocode:
        # https://en.wikipedia.org/wiki/Polish_notation#Order_of_operations
        stack = []
        for domain in reversed(domains):
            if isinstance(domain, tuple):
                # evaluate operand and push to stack
                if domain[1] == "in":
                    if not set(domain[2]) & set(value_ids):
                        stack.append(False)
                        continue
                else:
                    if set(domain[2]) & set(value_ids):
                        stack.append(False)
                        continue
                stack.append(True)
            else:
                # evaluate operator and previous 2 operands
                # compute_domain() only inserts 'or' operators
                # compute_domain() enforces 2 operands per operator
                operand1 = stack.pop()
                operand2 = stack.pop()
                stack.append(operand1 or operand2)

        # 'and' operator is implied for remaining stack elements
        avail = True
        while stack:
            avail &= stack.pop()
        return avail

    @api.model
    def values_available(
        self,
        check_val_ids=None,
        value_ids=None,
        custom_vals=None,
        product_tmpl_id=None,
        product_template_attribute_line_id=None,
    ):
        """Determines whether the attr_values from the product_template
        are available for selection given the configuration ids and the
        dependencies set on the product template

        :param check_val_ids: list of attribute value ids to check for
                              availability
        :param value_ids: list of attribute value ids
        :param custom_vals: custom values dict {attr_id: custom_val}

        :returns: list of available attribute values
        """
        if check_val_ids is None:
            check_val_ids = self.value_ids.ids
        elif check_val_ids:
            check_val_ids = check_val_ids.copy()
        if not self.product_tmpl_id:
            product_tmpl = self.env["product.template"].browse(product_tmpl_id)
        else:
            product_tmpl = self.product_tmpl_id

        product_tmpl.ensure_one()

        if product_template_attribute_line_id is not None:
            product_template_attribute_lines = self.env[
                "product.template.attribute.line"
            ].browse(product_template_attribute_line_id)
        else:
            product_template_attribute_lines = product_tmpl.attribute_line_ids

        if value_ids is None:
            value_ids = self.value_ids.ids
        elif value_ids:
            value_ids = value_ids.copy()

        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()

        avail_val_ids = []
        for attr_val_id in check_val_ids:
            config_lines = product_tmpl.config_line_ids.filtered(
                lambda line, attr_val_id=attr_val_id: attr_val_id in line.value_ids.ids
            )
            if product_template_attribute_lines:
                config_lines = config_lines.filtered(
                    lambda line: line.attribute_line_id
                    in product_template_attribute_lines
                )
            domains = config_lines.mapped("domain_id").compute_domain()
            avail = self.validate_domains_against_sels(domains, value_ids, custom_vals)
            if avail:
                avail_val_ids.append(attr_val_id)
            elif attr_val_id in value_ids:
                value_ids.remove(attr_val_id)

        return avail_val_ids

    @api.model
    def get_extra_attribute_line_ids(self, product_template_id):
        """Retrieve attribute lines defined on the product_template_id
        which are not assigned to configuration steps"""

        extra_attribute_line_ids = (
            product_template_id.attribute_line_ids
            - product_template_id.config_step_line_ids.mapped("attribute_line_ids")
        )
        return extra_attribute_line_ids

    def check_attributes_configuration(
        self, attribute_line_ids, custom_vals, value_ids, final=True
    ):
        for line in attribute_line_ids:
            # Validate custom values
            attr = line.attribute_id
            if attr.id in custom_vals:
                # ⚠️ La validation porte sur la LIGNE, pas sur l'attribut global
                # (D-089) — et elle reçoit la configuration courante, sans quoi
                # une borne conditionnelle n'aurait aucun moyen de se choisir.
                line.validate_custom_val(
                    custom_vals[attr.id], value_ids=value_ids, custom_vals=custom_vals
                )
            if final:
                line_values = line._configurator_value_ids()
                common_vals = set(value_ids) & set(line_values.ids)
                custom_val = custom_vals.get(attr.id)
                avail_val_ids = self.values_available(
                    check_val_ids=line_values.ids,
                    value_ids=value_ids,
                    product_tmpl_id=self.product_tmpl_id,
                    product_template_attribute_line_id=line.id,
                )
                if (
                    line.required
                    and avail_val_ids
                    and not common_vals
                    and not custom_val
                ):
                    # TODO: Verify custom value type to be correct
                    raise ValidationError(
                        self.env._("Required attribute '%s' is empty", attr.name)
                    )

    @api.model
    def validate_configuration(
        self,
        value_ids=None,
        custom_vals=None,
        product_tmpl_id=False,
        final=True,
    ):
        """Verifies if the configuration values passed via value_ids and
        custom_vals are valid

        :param value_ids: list of attribute value ids
        :param custom_vals: custom values dict {attr_id: custom_val}
        :param final: boolean marker to check required attributes.
                      pass false to check non-final configurations

        :returns: Error dict with reason of validation failure
                  or True
        """
        # TODO: Raise ConfigurationError with reason
        # Check if required values are missing for final configuration
        if value_ids is None:
            value_ids = self.value_ids.ids

        if product_tmpl_id:
            product_tmpl = self.env["product.template"].browse(product_tmpl_id)
        else:
            product_tmpl = self.product_tmpl_id

        product_tmpl.ensure_one()

        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()
        open_step_lines = self.get_open_step_lines()
        attribute_line_ids = open_step_lines.mapped("attribute_line_ids")
        attribute_line_ids += self.get_extra_attribute_line_ids(
            product_template_id=product_tmpl
        )
        # ⚠️ Un attribut masqué qui reste OBLIGATOIRE bloque la configuration
        # sans que rien ne s'affiche pour le débloquer. La visibilité doit donc
        # être tranchée AVANT l'exigence, jamais après (D-086, esprit de D-078).
        attribute_line_ids = attribute_line_ids.filtered(
            lambda line: line._is_visible(value_ids, custom_vals)
        )
        self.check_attributes_configuration(
            attribute_line_ids, custom_vals, value_ids, final=final
        )

        # Check if all the values passed are not restricted
        avail_val_ids = self.values_available(
            value_ids, value_ids, product_tmpl_id=product_tmpl_id
        )
        if set(value_ids) - set(avail_val_ids):
            restrict_val = list(set(value_ids) - set(avail_val_ids))
            product_att_values = self.env["product.attribute.value"].browse(
                restrict_val
            )
            group_by_attr = {}
            for val in product_att_values:
                if val.attribute_id in group_by_attr:
                    group_by_attr[val.attribute_id] += val
                else:
                    group_by_attr[val.attribute_id] = val

            message = self.env._("The following values are not available:")
            for attr, val in group_by_attr.items():
                message += "\n {}: {}".format(attr.name, ", ".join(val.mapped("name")))
            raise ValidationError(message)

        # Check if custom values are allowed
        custom_attr_ids = (
            product_tmpl.attribute_line_ids.filtered("custom")
            .mapped("attribute_id")
            .ids
        )
        if not set(custom_vals.keys()) <= set(custom_attr_ids):
            custom_attrs_with_error = list(
                set(custom_vals.keys()) - set(custom_attr_ids)
            )
            custom_attrs_with_error = self.env["product.attribute"].browse(
                custom_attrs_with_error
            )
            error_message = self.env._(
                "The following custom values are not permitted "
                "according to the product template - %s.\n\nIt is possible "
                "that a change has been made to allowed custom values "
                "while your configuration was in process. Please reset your "
                "current session and start over or contact your administrator"
                " in order to proceed."
            )
            message_vals = ""
            for attr_id in custom_attrs_with_error:
                message_vals += f"\n {attr_id.name}: {custom_vals.get(attr_id.id)}"
            raise ValidationError(error_message % (message_vals))

        # Check if there are multiple values passed for non-multi attributes
        mono_attr_lines = product_tmpl.attribute_line_ids.filtered(
            lambda line: not line.multi
        )
        attrs_with_error = {}
        for line in mono_attr_lines:
            if len(set(line.value_ids.ids) & set(value_ids)) > 1:
                wrong_vals = self.env["product.attribute.value"].browse(
                    set(line.value_ids.ids) & set(value_ids)
                )
                attrs_with_error[line.attribute_id] = wrong_vals
        if attrs_with_error:
            error_message = self.env._(
                "The following multi values are not permitted "
                "according to the product template - %s.\n\nIt is possible "
                "that a change has been made to allowed multi values "
                "while your configuration was in process. Please reset your "
                "current session and start over or contact your administrator"
                " in order to proceed."
            )
            message_vals = ""
            for attr_id, vals in attrs_with_error.items():
                message_vals += "\n {}: {}".format(
                    attr_id.name, ", ".join(vals.mapped("name"))
                )
            raise ValidationError(error_message % (message_vals))
        return True

    @api.model
    def search_variant(self, value_ids=None, product_tmpl_id=None):
        """Searches product.variants with given value_ids and custom values
        given in the custom_vals dict

        :param value_ids: list of product.attribute.values ids
        :param custom_vals: dict {product.attribute.id: custom_value}

        :returns: product.product recordset of products matching domain
        """
        if value_ids is None:
            value_ids = self.value_ids.ids

        custom_value_id = self.get_custom_value_id()
        value_ids = list(set(value_ids) - set(custom_value_id.ids))

        if not product_tmpl_id:
            product_tmpl_id = self.product_tmpl_id
            if not product_tmpl_id:
                raise ValidationError(
                    self.env._(
                        "Cannot conduct search on an empty config session "
                        "without product_tmpl_id kwarg"
                    )
                )

        domain = self.get_variant_search_domain(
            product_tmpl_id=product_tmpl_id, value_ids=value_ids
        )
        products = self.env["product.product"].search(domain)

        # At this point, we might have found products with all of the passed
        # in values, but it might have more attributes!  These are NOT
        # matches
        more_attrs = products.filtered(
            lambda p: len(p.product_template_attribute_value_ids) != len(value_ids)
        )
        products -= more_attrs
        return products

    def search_session(self, product_tmpl_id, parent_id=None):
        domain = self.get_session_search_domain(
            product_tmpl_id=product_tmpl_id, parent_id=parent_id
        )
        session = self.search(domain, order="create_date desc", limit=1)
        return session

    @api.model
    def create_get_session(
        self, product_tmpl_id, parent_id=None, force_create=False, user_id=None
    ):
        if not force_create:
            session = self.search_session(
                product_tmpl_id=product_tmpl_id, parent_id=parent_id
            )
            if session:
                return session
        vals = self.get_session_vals(
            product_tmpl_id=product_tmpl_id,
            parent_id=parent_id,
            user_id=user_id,
        )
        return self.create(vals)

    # TODO: Disallow duplicates
    def flatten_val_ids(self, value_ids):
        """Return a list of value_ids from a list with a mix of ids
        and list of ids (multiselection)

        :param value_ids: list of value ids or mix of ids and list of ids
                           (e.g: [1, 2, 3, [4, 5, 6]])
        :returns: flattened list of ids ([1, 2, 3, 4, 5, 6])"""
        if not isinstance(value_ids, list | tuple):
            return [value_ids]  # Ensure single values are wrapped in a list

        flat_val_ids = set(self.flatten_attribute_value_ids(value_ids))
        return list(flat_val_ids)

    def formatPrices(self, prices=None, dp="Product Price"):
        if prices is None:
            prices = {}
        dp = None
        prices["taxes"] = formatLang(self.env, prices["taxes"], monetary=True, dp=dp)
        prices["total"] = formatLang(self.env, prices["total"], monetary=True, dp=dp)
        prices["vals"] = [
            (v[0], v[1], formatLang(self.env, v[2], monetary=True, dp=dp))
            for v in prices["vals"]
        ]
        return prices

    @api.model
    def get_child_specification(self, model, parent):
        """return dictiory of onchange specification by
        appending parent before each key"""
        model_obj = self.env[model]
        specs = model_obj._onchange_spec()
        new_specs = {}
        for key, val in specs.items():
            new_specs[f"{parent}.{key}"] = val
        return new_specs

    @api.model
    def get_onchange_specifications(self, model):
        """return onchange specification
        - same functionality by _onchange_spec
        - needed this method because odoo don't add specification for fields
        one2many or many2many there is view-reference(using : tree_view_ref)
        intead of view in that field"""
        if not model:
            return {}
        model_obj = self.env.get(model)
        specs = model_obj._onchange_spec()
        for name, field in model_obj._fields.items():
            if field.type not in ["one2many", "many2many"]:
                continue
            ch_specs = self.get_child_specification(
                model=field.comodel_name, parent=name
            )
            specs.update(ch_specs)
        return specs

    @api.model
    def get_vals_to_write(self, values, model):
        """Return values in formate excepted by write/create methods
        - same functionality by _convert_to_write
        - needed this method because odoo don't call convert to write
        for the many2many/one2many fields"""
        model_obj = self.env[model]
        values = model_obj._convert_to_write(values)
        fields = model_obj._fields
        for key, vals in values.items():
            if not isinstance(vals, list):
                continue
            new_lst = []
            for line in vals:
                new_line = line
                if line and isinstance(line[-1], dict):
                    new_line = line[:-1] + (
                        self.get_vals_to_write(
                            values=line[-1], model=fields[key].comodel_name
                        ),
                    )
                new_lst.append(new_line)
            values[key] = new_lst
        return values


class ProductConfigSessionCustomValue(models.Model):
    _name = "product.config.session.custom.value"
    _rec_name = "attribute_id"
    _description = "Product Config Session Custom Value"

    @api.depends("value", "attribute_id", "attribute_id.uom_id")
    def _compute_val_name(self):
        # La valeur est le NOMBRE, l'affichage porte l'unité — et la mise en
        # forme vient de l'attribut, pas d'ici : c'est la même partout.
        # ⚠️ `value` manquait au `depends` : renseigner une valeur ne
        # recalculait pas son libellé.
        for attr_val_custom in self:
            attr_val_custom.name = attr_val_custom.attribute_id.format_custom_value(
                attr_val_custom.value
            )

    name = fields.Char(readonly=True, compute="_compute_val_name", store=True)
    attribute_id = fields.Many2one(
        comodel_name="product.attribute", string="Attribute", required=True
    )
    cfg_session_id = fields.Many2one(
        comodel_name="product.config.session",
        required=True,
        ondelete="cascade",
        string="Session",
    )
    value = fields.Char(help="Custom value held as string")
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="product_config_session_custom_value_attachment_rel",
        column1="cfg_sesion_custom_val_id",
        column2="attachment_id",
        string="Attachments",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Range le nombre sous sa forme canonique AVANT qu'il touche la base.

        Le faire à l'écriture et non à l'affichage est ce qui rend deux saisies
        de la même largeur ÉGALES : `2400` et `2400.0` ne doivent pas devenir
        deux valeurs distinctes le jour du rangement en valeur d'attribut
        (D-081).
        """
        for vals in vals_list:
            if "value" in vals and vals.get("attribute_id"):
                attribute = self.env["product.attribute"].browse(vals["attribute_id"])
                vals["value"] = attribute.canonical_custom_value(vals["value"])
        return super().create(vals_list)

    def write(self, vals):
        if "value" not in vals:
            return super().write(vals)
        # ⚠️ Un seul `vals` pour des attributs différents : la forme canonique
        # dépend de l'attribut, donc l'écriture se fait par groupe. Prendre
        # `self.attribute_id` sans grouper ne rendrait rien dès le second
        # attribut, et la mise en forme sauterait EN SILENCE.
        result = True
        for attribute, records in self.grouped("attribute_id").items():
            canonical = dict(
                vals, value=attribute.canonical_custom_value(vals["value"])
            )
            result = (
                super(ProductConfigSessionCustomValue, records).write(canonical)
                and result
            )
        return result

    def eval(self):
        """Return custom value evaluated using the related custom field type"""
        field_type = self.attribute_id.custom_type
        if field_type == "binary":
            vals = self.attachment_ids.mapped("datas")
            if len(vals) == 1:
                return vals[0]
            return vals
        elif field_type == "integer":
            return int(self.value)
        elif field_type == "float":
            return float(self.value)
        return self.value

    @api.constrains("cfg_session_id", "attribute_id")
    def unique_attribute(self):
        for custom_val in self:
            values = custom_val.cfg_session_id.custom_value_ids
            if (
                len(
                    values.filtered(
                        lambda x, custom_val=custom_val: x.attribute_id
                        == custom_val.attribute_id
                    )
                )
                > 1
            ):
                raise ValidationError(
                    self.env._(
                        "Configuration cannot have the " "same value inserted twice"
                    )
                )

    # @api.constrains('cfg_session_id.value_ids')
    # def custom_only(self):
    #     """Verify that the attribute_id is not present in vals as well"""
    #     import ipdb;ipdb.set_trace()
    #     if self.cfg_session_id.value_ids.filtered(
    #             lambda x: x.attribute_id == self.attribute_id):
    #         raise ValidationError(
    #             _("Configuration cannot have a selected option and a custom "
    #               "value with the same attribute")
    #         )

    @api.constrains("attachment_ids", "value")
    def check_custom_type(self):
        for custom_val in self:
            custom_type = custom_val.attribute_id.custom_type
            if custom_val.value and custom_type == "binary":
                raise ValidationError(
                    self.env._(
                        "Attribute custom type is binary, attachments are the "
                        "only accepted values with this custom field type"
                    )
                )
            if custom_val.attachment_ids and custom_type != "binary":
                raise ValidationError(
                    self.env._(
                        "Attribute custom type must be 'binary' for saving "
                        "attachments to custom value"
                    )
                )
