import logging
from io import StringIO

from mako.runtime import Context
from mako.template import Template

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.depends("product_variant_ids.product_tmpl_id")
    def _compute_product_variant_count(self):
        """For configurable products return the number of variants configured or
        1 as many views and methods trigger only when a template has at least
        one variant attached. Since we create them from the template we should
        have access to them always"""
        result = super()._compute_product_variant_count()
        for product_tmpl in self:
            config_ok = product_tmpl.config_ok
            variant_count = product_tmpl.product_variant_count
            if config_ok and not variant_count:
                product_tmpl.product_variant_count = 1
        return result

    @api.depends("attribute_line_ids.value_ids")
    def _compute_template_attr_vals(self):
        """Compute all attribute values added in attribute line on
        product template"""
        for product_tmpl in self:
            if product_tmpl.config_ok:
                value_ids = product_tmpl.attribute_line_ids.mapped("value_ids")
                product_tmpl.attribute_line_val_ids = value_ids
            else:
                product_tmpl.attribute_line_val_ids = False

    @api.constrains("attribute_line_ids", "attribute_value_line_ids")
    def check_attr_value_ids(self):
        """Check attribute lines don't have some attribute value that
        is not present in attribute lines of that product template"""
        for product_tmpl in self:
            if not product_tmpl.env.context.get("check_constraint", True):
                continue
            attr_val_lines = product_tmpl.attribute_value_line_ids
            attr_val_ids = attr_val_lines.mapped("value_ids")
            if not attr_val_ids <= product_tmpl.attribute_line_val_ids:
                raise ValidationError(
                    self.env._(
                        "All attribute values used in attribute value lines "
                        "must be defined in the attribute lines of the "
                        "template"
                    )
                )

    @api.constrains("attribute_value_line_ids")
    def _validate_unique_config(self):
        """Check for duplicate configurations for the same
        attribute value in image lines"""
        for template in self:
            attr_val_line_vals = template.attribute_value_line_ids.read(
                ["value_id", "value_ids"], load=False
            )
            attr_val_line_vals = [
                (line["value_id"], tuple(line["value_ids"]))
                for line in attr_val_line_vals
            ]
            if len(set(attr_val_line_vals)) != len(attr_val_line_vals):
                raise ValidationError(
                    self.env._(
                        "You cannot have a duplicate configuration for the same value"
                    )
                )

    config_ok = fields.Boolean(string="Can be Configured")

    config_line_ids = fields.One2many(
        comodel_name="product.config.line",
        inverse_name="product_tmpl_id",
        string="Attribute Dependencies",
        copy=False,
    )

    config_image_ids = fields.One2many(
        comodel_name="product.config.image",
        inverse_name="product_tmpl_id",
        string="Configuration Images",
        copy=True,
    )

    attribute_value_line_ids = fields.One2many(
        comodel_name="product.attribute.value.line",
        inverse_name="product_tmpl_id",
        string="Attribute Value Lines",
        copy=True,
    )

    attribute_line_val_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        compute="_compute_template_attr_vals",
        store=False,
    )

    config_step_line_ids = fields.One2many(
        comodel_name="product.config.step.line",
        inverse_name="product_tmpl_id",
        string="Configuration Lines",
        copy=False,
    )

    mako_tmpl_name = fields.Text(
        string="Variant name",
        help="Generate Name based on Mako Template",
        copy=True,
    )

    # We are calculating weight of variants based on weight of
    # product-template so that no need of compute and inverse on this
    weight = fields.Float(
        compute="_compute_weight",
        inverse="_set_weight",  # pylint: disable=C8110
        search="_search_weight",
        store=False,
    )
    weight_dummy = fields.Float(
        string="Manual Weight",
        digits="Stock Weight",
        help="Manual setting of product template weight",
    )

    def _compute_weight(self):
        config_products = self.filtered(lambda template: template.config_ok)
        for product in config_products:
            product.weight = product.weight_dummy
        standard_products = self - config_products
        return super(ProductTemplate, standard_products)._compute_weight()

    def _set_weight(self):
        for product_tmpl in self:
            product_tmpl.weight_dummy = product_tmpl.weight
            if not product_tmpl.config_ok:
                super(ProductTemplate, product_tmpl)._set_weight()
        return

    def _search_weight(self, operator, value):
        return [("weight_dummy", operator, value)]

    def _check_default_values(self):
        default_val_ids = (
            self.attribute_line_ids.filtered(lambda line: line.default_val)
            .mapped("default_val")
            .ids
        )

        cfg_session_obj = self.env["product.config.session"]
        try:
            cfg_session_obj.validate_configuration(
                value_ids=default_val_ids, product_tmpl_id=self.id, final=False
            )
        except ValidationError as exc:
            raise ValidationError(exc.args[0]) from exc
        except Exception as exc:
            raise ValidationError(
                self.env._("Default values provided generate an invalid configuration")
            ) from exc

    @api.constrains("config_line_ids", "attribute_line_ids")
    def _check_default_value_domains(self):
        for template in self:
            try:
                template._check_default_values()
            except ValidationError as exc:
                raise ValidationError(
                    self.env._(
                        "Restrictions added make the current default values "
                        "generate an invalid configuration.\
                      \n%s"
                    )
                    % (exc.args[0])
                ) from exc

    def toggle_config(self):
        for record in self:
            record.config_ok = not record.config_ok

    def _create_variant_ids(self):
        """Prevent configurable products from creating variants as these serve
        only as a template for the product configurator"""
        templates = self.filtered(lambda t: not t.config_ok)
        if not templates:
            return None
        return super(ProductTemplate, templates)._create_variant_ids()

    def unlink(self):
        """- Prevent the removal of configurable product templates
            from variants
        - Patch for check access rights of user(configurable products)"""
        configurable_templates = self.filtered(lambda template: template.config_ok)
        if configurable_templates:
            configurable_templates[:1].check_config_user_access()
        for config_template in configurable_templates:
            variant_unlink = config_template.env.context.get(
                "unlink_from_variant", False
            )
            if variant_unlink:
                self -= config_template
        res = super().unlink()
        return res

    def copy(self, default=None):
        """Copy restrictions, config Steps and attribute lines
        ith product template"""
        if not default:
            default = {}
        self = self.with_context(check_constraint=False)
        res = super().copy(default=default)

        # Attribute lines
        attribute_line_dict = {}
        for line in res.attribute_line_ids:
            attribute_line_dict.update({line.attribute_id.id: line.id})

        # Restrictions
        for line in self.config_line_ids:
            old_restriction = line.domain_id
            new_restriction = old_restriction.copy()
            config_line_default = {
                "product_tmpl_id": res.id,
                "domain_id": new_restriction.id,
            }
            new_attribute_line_id = attribute_line_dict.get(
                line.attribute_line_id.attribute_id.id, False
            )
            if not new_attribute_line_id:
                continue
            config_line_default.update({"attribute_line_id": new_attribute_line_id})
            line.copy(config_line_default)

        # Config steps
        config_step_line_default = {"product_tmpl_id": res.id}
        for line in self.config_step_line_ids:
            new_attribute_line_ids = [
                attribute_line_dict.get(old_attr_line.attribute_id.id)
                for old_attr_line in line.attribute_line_ids
                if old_attr_line.attribute_id.id in attribute_line_dict
            ]
            if new_attribute_line_ids:
                config_step_line_default.update(
                    {"attribute_line_ids": [(6, 0, new_attribute_line_ids)]}
                )
            line.copy(config_step_line_default)
        return res

    def configure_product(self):
        """launches a product configurator wizard with a linked
        template in order to configure new product."""
        return self.with_context(product_tmpl_id_readonly=True).create_config_wizard(
            click_next=False
        )

    def create_config_wizard(
        self,
        model_name="product.configurator",
        extra_vals=None,
        click_next=True,
    ):
        """create product configuration wizard
        - return action to launch wizard
        - click on next step based on value of click_next"""
        wizard_obj = self.env[model_name]
        wizard_vals = {"product_tmpl_id": self.id}
        if extra_vals:
            wizard_vals.update(extra_vals)
        wizard = wizard_obj.create(wizard_vals)
        if click_next:
            action = wizard.action_next_step()
        else:
            wizard_obj = wizard_obj.with_context(
                wizard_model=model_name,
                allow_preset_selection=True,
            )
            action = wizard_obj.get_wizard_action(wizard=wizard)
        return action

    @api.model
    def _check_config_group_rights(self):
        """Return True/False from system parameter
        - Signals access rights needs to check or not
        :Params: return : boolean"""
        ICPSudo = self.env["ir.config_parameter"].sudo()
        manager_product_configuration_settings = ICPSudo.get_param(
            "product_configurator_fa.manager_product_configuration_settings"
        )
        return manager_product_configuration_settings

    @api.model
    def check_config_user_access(self):
        """Check user have access to perform action(create/write/delete)
        on configurable products"""
        if not self._check_config_group_rights():
            return True
        config_manager = self.env.user.has_group(
            "product_configurator_fa.group_product_configurator_fa_manager"
        )
        user_root = self.env.ref("base.user_root")
        user_admin = self.env.ref("base.user_admin")
        if (
            config_manager
            or self.env.user.id in [user_root.id, user_admin.id]
            or self.env.su
        ):
            return True
        raise ValidationError(
            self.env._(
                "Sorry, you are not allowed to create/change this kind of "
                "document. For more information please contact your manager."
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        """Patch for check access rights of user(configurable products)"""
        for vals in vals_list:
            config_ok = vals.get("config_ok", False)
            if config_ok:
                self.check_config_user_access()
        return super().create(vals_list)

    def write(self, vals):
        """Patch for check access rights of user(configurable products)"""
        change_config_ok = "config_ok" in vals
        configurable_templates = self.filtered(lambda template: template.config_ok)
        if change_config_ok or configurable_templates:
            self[:1].check_config_user_access()

        return super().write(vals)

    @api.constrains("config_line_ids")
    def _check_config_line_domain(self):
        attribute_line_ids = self.attribute_line_ids
        tmpl_value_ids = attribute_line_ids._configurator_value_ids()
        tmpl_attribute_ids = attribute_line_ids.mapped("attribute_id")
        error_message = False
        for domain_id in self.config_line_ids.mapped("domain_id"):
            domain_attr_ids = domain_id.domain_line_ids.mapped("attribute_id")
            domain_value_ids = domain_id.domain_line_ids.mapped("value_ids")
            invalid_value_ids = domain_value_ids - tmpl_value_ids
            invalid_attribute_ids = domain_attr_ids - tmpl_attribute_ids
            if not invalid_attribute_ids and not invalid_value_ids:
                continue
            if not error_message:
                error_message = self.env._(
                    "Following Attribute/Value from restriction "
                    "are not present in template attributes/values. "
                    "Please make sure you are adding right restriction"
                )
            error_message += self.env._("\nRestriction: %s", domain_id.name)
            error_message += (
                invalid_attribute_ids
                and self.env._(
                    "\nAttribute/s: %s", ", ".join(invalid_attribute_ids.mapped("name"))
                )
                or ""
            )
            error_message += (
                invalid_value_ids
                and self.env._(
                    "\nValue/s: %s\n", ", ".join(invalid_value_ids.mapped("name"))
                )
                or ""
            )
        if error_message:
            raise ValidationError(error_message)


    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Décrit les ATTRIBUTS d'un produit comme des champs — D-097.

        C'est tout ce dont le `DomainSelector` a besoin : il n'appelle qu'une
        chose, `fields_get` (`web/static/src/core/field_service.js:17`). Sans
        cela il propose les champs techniques de `product.template` — « Image
        1024 », « Estimation par Lot/Numéro de série » — et un utilisateur
        métier n'en fait rien.

        ⚠️ **Sous CONTEXTE, jamais partout.** Ces champs n'existent pas : les
        exposer à tout appel de `fields_get` les ferait apparaître dans les
        vues, les exports et les filtres, où plus rien ne saurait les lire.

        ⚠️ Tous les attributs sont décrits en `many2one` vers une VALEUR, y
        compris les numériques — parce que le stockage d'OCA ne connaît que
        `in` / `not in` sur des valeurs (D-080). Décrire une dimension en
        `float` laisserait construire `largeur > 4000`, que l'enregistrement
        perdrait en silence.
        """
        fields = super().fields_get(allfields=allfields, attributes=attributes)
        template_id = self.env.context.get("configurator_domain_tmpl_id")
        if not template_id:
            return fields
        domain_obj = self.env["product.config.domain"]
        template = self.browse(template_id)
        for line in template.attribute_line_ids:
            attribute = line.attribute_id
            fields[domain_obj._attribute_field_name(attribute)] = {
                "string": attribute.name,
                "type": "many2one",
                "relation": "product.attribute.value",
                "domain": [("attribute_id", "=", attribute.id)],
                "searchable": True,
                "sortable": False,
                "store": False,
                "readonly": True,
            }
        return fields

    price_grid_ids = fields.One2many(
        comodel_name="product.price.grid",
        inverse_name="product_tmpl_id",
        string="Price Grids",
    )
    price_grid_warning = fields.Char(compute="_compute_price_grid_warning")

    @api.depends("config_ok", "price_grid_ids", "price_grid_ids.active")
    def _compute_price_grid_warning(self):
        """L'absence de grille se signale À L'ARRIVÉE dans le produit — D-083.

        Et non au moment du devis : on ne laisse pas quelqu'un configurer dix
        minutes pour lui annoncer ensuite qu'on ne sait pas vendre.
        """
        for template in self:
            missing = template.config_ok and not template.price_grid_ids
            template.price_grid_warning = (
                self.env._(
                    "This configurable product has no price grid: it cannot be "
                    "quoted until one is set."
                )
                if missing
                else False
            )

    def _get_price_grid(self, date=None):
        """La grille en vigueur à cette date — au plus une (D-083)."""
        self.ensure_one()
        # ⚠️ Odoo passe la date tantôt en `date`, tantôt en chaîne (un contexte,
        # une valeur de devis) : comparer sans convertir lève un TypeError que
        # rien n'annonce à la lecture.
        date = fields.Date.to_date(date) or fields.Date.context_today(self)
        grids = self.price_grid_ids.filtered(
            lambda grid: (not grid.date_start or grid.date_start <= date)
            and (not grid.date_end or grid.date_end >= date)
        )
        return grids[:1]

    def _grid_axis_lines(self):
        """Les deux lignes d'attribut qui portent les rôles d'axe — D-098."""
        self.ensure_one()
        lines = {}
        for line in self.attribute_line_ids:
            if line.dimension_role:
                lines[line.dimension_role] = line
        return lines

    def _grid_surface(self, x_value, y_value):
        """La surface en m² — le PRODUIT DES DEUX AXES, rien d'autre (D-161).

        ⚠️ Première conversion d'unités du module : D-160 pose qu'un attribut
        porte une unité et que personne ne convertit, mais 2 400 mm × 2 100 mm
        ne fait pas 5 040 000 m². Un axe SANS unité est refusé plutôt que
        supposé en millimètres — supposer ici, c'est se tromper d'un facteur
        un million sans que rien ne le dise.
        """
        self.ensure_one()
        axis_lines = self._grid_axis_lines()
        metres = []
        for role, value in (("axis_x", x_value), ("axis_y", y_value)):
            line = axis_lines.get(role)
            uom = line.attribute_id.uom_id if line else False
            if not uom:
                raise ValidationError(
                    self.env._(
                        "A surface cannot be computed on %(product)s: the grid "
                        "axis has no unit of measure.",
                        product=self.display_name,
                    )
                )
            reference = uom.category_id.uom_ids.filtered(
                lambda unit: unit.uom_type == "reference"
            )
            if not reference:
                raise ValidationError(
                    self.env._("The unit %(uom)s has no reference unit", uom=uom.name)
                )
            metres.append(uom._compute_quantity(value, reference, round=False))
        return metres[0] * metres[1]

    def _refresh_grid_list_price(self):
        """Le `list_price` du template devient le « À PARTIR DE » — D-093.

        Sans cela, la fiche annoncerait « Prix de vente : 200 € » alors
        qu'aucune vente ne se ferait à ce prix.
        """
        for template in self:
            grid = template._get_price_grid()
            if grid:
                template.list_price = grid._lowest_price()


class ProductProduct(models.Model):
    _inherit = "product.product"
    _rec_name = "config_name"

    grid_price = fields.Float(
        string="Grid Price",
        digits="Product Price",
        readonly=True,
        help="Price read in the grid in force TODAY. Informative only — a "
        "quotation always reads the grid at its own date.",
    )

    def _get_grid_dimensions(self):
        """Les deux cotes de cette variante, lues dans ses valeurs d'attribut.

        Elles y sont parce que le lot 2 les y a rangées (D-081) : une dimension
        n'est pas une valeur personnalisée, c'est une valeur d'attribut — et
        c'est ce qui la rend lisible ici, sans session ni saisie.
        """
        self.ensure_one()
        dimensions = {}
        for ptav in self.product_template_attribute_value_ids:
            role = ptav.attribute_line_id.dimension_role
            if not role:
                continue
            try:
                dimensions[role] = float(ptav.product_attribute_value_id.name)
            except (TypeError, ValueError):
                # Une valeur d'axe qui n'est pas un nombre ne dit rien : mieux
                # vaut pas de prix de grille qu'un prix lu de travers.
                return {}
        return dimensions

    def _get_grid_price(self, date=None):
        """Le prix de grille de cette variante, ou `None` — jamais zéro."""
        self.ensure_one()
        grid = self.product_tmpl_id._get_price_grid(date=date)
        if not grid:
            return None
        dimensions = self._get_grid_dimensions()
        if "axis_x" not in dimensions or "axis_y" not in dimensions:
            return None
        return grid.get_price(dimensions["axis_x"], dimensions["axis_y"])

    def _get_attributes_extra_price_sqm(self):
        """La part des suppléments exprimée AU MÈTRE CARRÉ — D-162.

        ⚠️ Elle ne peut pas passer par `price_extra`, que tout Odoo somme
        comme un montant : 25 €/m² y serait ajouté comme 25 €, sans erreur et
        sans trace.
        """
        self.ensure_one()
        rated = self.product_template_attribute_value_ids.filtered(
            lambda ptav: ptav.attribute_line_id.price_mode == "per_sqm"
            and ptav.price_extra_sqm
        )
        if not rated:
            return 0.0
        dimensions = self._get_grid_dimensions()
        if "axis_x" not in dimensions or "axis_y" not in dimensions:
            return 0.0
        surface = self.product_tmpl_id._grid_surface(
            dimensions["axis_x"], dimensions["axis_y"]
        )
        return sum(rated.mapped("price_extra_sqm")) * surface

    def _price_compute(
        self, price_type, uom=None, currency=None, company=None, date=False
    ):
        """Pour un produit à grille, `list_price` REND LE PRIX DE GRILLE — D-093.

        ⚠️ C'est le point unique par lequel tout Odoo demande le prix d'un
        produit : listes de prix, devis, rapports, portail. Une remise
        « professionnel −10 % » part de `list_price` (le défaut d'une règle) :
        sans cette surcharge, elle s'appliquerait aux 200 € du template au lieu
        des 540 € de la grille, et le devis afficherait un montant plausible.

        La « quatrième base » — ajouter `grid_price` aux choix de `base` d'une
        règle — a été écartée : il faudrait PENSER à la choisir, et l'oubli est
        silencieux.

        source : addons/product/models/product_product.py:794 — les étapes
        (extras, unité, devise) sont reprises telles quelles ; voir P1 et P2 du
        registre des points de contact.
        """
        if price_type != "list_price":
            return super()._price_compute(
                price_type, uom=uom, currency=currency, company=company, date=date
            )
        company = company or self.env.company
        date = date or fields.Date.context_today(self)
        prices = super()._price_compute(
            price_type, uom=uom, currency=currency, company=company, date=date
        )
        for product in self.with_company(company):
            grid_price = product._get_grid_price(date=date)
            if grid_price is None:
                continue
            price = (
                grid_price
                + product._get_attributes_extra_price()
                + product._get_attributes_extra_price_sqm()
            )
            if uom:
                price = product.uom_id._compute_price(price, uom)
            if currency:
                price = product.currency_id._convert(price, currency, company, date)
            prices[product.id] = price
        return prices

    @api.model
    def _cron_refresh_grid_price(self):
        """Rafraîchit le prix de grille STOCKÉ — informatif, jamais autorité.

        ⚠️ D-084 : une grille datée rend tout champ stocké faux le jour où un
        nouveau tarif prend effet. Ce champ dit « le prix en vigueur ce jour » ;
        entre minuit et ce passage, il est périmé. Acceptable pour un
        affichage, jamais pour un devis — qui lit la grille à SA date.
        """
        products = self.search([("config_ok", "=", True)])
        for product in products:
            grid_price = product._get_grid_price()
            if grid_price is not None and grid_price != product.grid_price:
                product.grid_price = grid_price

    @api.constrains("product_template_attribute_value_ids")
    def _check_duplicate_product(self):
        """Check for prducts with same attribute values/custom values"""
        for product in self:
            if not product.config_ok:
                continue

            # At the moment, I don't have enough confidence with my
            # understanding of binary attributes, so will leave these
            # as not matching...
            # In theory, they should just work, if they are set to "non search"
            # in custom field def!
            # TODO: Check the logic with binary attributes
            config_session_obj = product.env["product.config.session"]
            ptav_ids = product.product_template_attribute_value_ids.mapped(
                "product_attribute_value_id"
            )
            duplicates = config_session_obj.search_variant(
                product_tmpl_id=product.product_tmpl_id,
                value_ids=ptav_ids.ids,
            ).filtered(lambda p, product=product: p.id != product.id)

            if duplicates:
                raise ValidationError(
                    self.env._(
                        "Configurable Products cannot have duplicates "
                        "(identical attribute values)"
                    )
                )

    def _get_config_name(self):
        """Name for configured products
        :param: return : String"""
        self.ensure_one()
        return self.name

    def _get_mako_context(self, buf):
        """Return context needed for computing product name based
        on mako-tamplate define on it's product template"""
        self.ensure_one()
        ptav_ids = self.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id"
        )
        return Context(
            buf,
            product=self,
            attribute_values=ptav_ids,
            steps=self.product_tmpl_id.config_step_line_ids,
            template=self.product_tmpl_id,
        )

    def _get_mako_tmpl_name(self):
        """Compute and return product name based on mako-tamplate
        define on it's product template"""
        self.ensure_one()
        if self.mako_tmpl_name:
            try:
                mytemplate = Template(self.mako_tmpl_name or "")
                buf = StringIO()
                ctx = self._get_mako_context(buf)
                mytemplate.render_context(ctx)
                return buf.getvalue()
            except Exception:
                _logger.error(
                    self.env._("Error while calculating mako product name: %s")
                    % self.display_name
                )
        return self.display_name

    @api.depends("product_template_attribute_value_ids.weight_extra")
    def _compute_product_weight_extra(self):
        for product in self:
            product.weight_extra = sum(
                product.mapped("product_template_attribute_value_ids.weight_extra")
            )

    def _compute_product_weight(self):
        for product in self:
            if product.config_ok:
                tmpl_weight = product.product_tmpl_id.weight
                product.weight = tmpl_weight + product.weight_extra
            else:
                product.weight = product.weight_dummy

    def _search_product_weight(self, operator, value):
        return [("weight_dummy", operator, value)]

    def _inverse_product_weight(self):
        """Store weight in dummy field"""
        self.weight_dummy = self.weight

    config_name = fields.Char(
        string="Configuration Name", compute="_compute_config_name"
    )
    weight_extra = fields.Float(compute="_compute_product_weight_extra")
    weight_dummy = fields.Float(string="Manual Weight", digits="Stock Weight")
    weight = fields.Float(
        compute="_compute_product_weight",
        inverse="_inverse_product_weight",
        search="_search_product_weight",
        store=False,
    )

    # product preset
    config_preset_ok = fields.Boolean(string="Is Preset")

    def _compute_config_name(self):
        """Compute the name of the configurable products and use template
        name for others"""
        for product in self:
            if product.config_ok:
                product.config_name = product._get_config_name()
            else:
                product.config_name = product.name

    def reconfigure_product(self):
        """launches a product configurator wizard with a linked
        template and variant in order to re-configure an existing product.
        It is essentially a shortcut to pre-fill configuration
        data of a variant"""
        self.ensure_one()

        extra_vals = {"product_id": self.id}
        return self.product_tmpl_id.create_config_wizard(extra_vals=extra_vals)

    @api.model
    def check_config_user_access(self, mode):
        """Check user have access to perform action(create/write/delete)
        on configurable products"""
        if not self.env["product.template"]._check_config_group_rights():
            return True
        config_manager = self.env.user.has_group(
            "product_configurator_fa.group_product_configurator_fa_manager"
        )
        config_user = self.env.user.has_group(
            "product_configurator_fa.group_product_configurator_fa"
        )
        user_root = self.env.ref("base.user_root")
        user_admin = self.env.ref("base.user_admin")
        if (
            config_manager
            or (config_user and mode not in ["delete"])
            or self.env.user.id in [user_root.id, user_admin.id]
        ):
            return True
        raise ValidationError(
            self.env._(
                "Sorry, you are not allowed to create/change this kind of "
                "document. For more information please contact your manager."
            )
        )

    def unlink(self):
        """- Signal unlink from product variant through context so
        removal can be stopped for configurable templates
        - check access rights of user(configurable products)"""
        config_product = any(p.config_ok for p in self)
        if config_product:
            self.env["product.product"].check_config_user_access(mode="delete")
        ctx = dict(self.env.context, unlink_from_variant=True)
        self.env.context = ctx
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        """Patch for check access rights of user(configurable products)"""
        for vals in vals_list:
            config_ok = vals.get("config_ok", False)
            if config_ok:
                self.check_config_user_access(mode="create")
        return super().create(vals_list)

    def write(self, vals):
        """Patch for check access rights of user(configurable products)"""
        change_config_ok = "config_ok" in vals
        configurable_products = self.filtered(lambda product: product.config_ok)
        if change_config_ok or configurable_products:
            self[:1].check_config_user_access(mode="write")

        return super().write(vals)

    def _compute_product_price_extra(self):
        standard_products = self.filtered(lambda product: not product.config_ok)
        config_products = self - standard_products
        if standard_products:
            result = super(
                ProductProduct, standard_products
            )._compute_product_price_extra()
        else:
            result = None
        for product in config_products:
            attribute_value_obj = self.env["product.attribute.value"]
            value_ids = (
                product.product_template_attribute_value_ids.product_attribute_value_id
            )
            extra_prices = attribute_value_obj.get_attribute_value_extra_prices(
                product_tmpl_id=product.product_tmpl_id.id, pt_attr_value_ids=value_ids
            )
            product.price_extra = sum(extra_prices.values())
        return result
