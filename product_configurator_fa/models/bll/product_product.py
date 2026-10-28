"""Ce qu'exécute `product.product` (BLL, D-541)."""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

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

    def _compute_config_name(self):
        """Compute the name of the configurable products and use template
        name for others"""
        for product in self:
            if product.config_ok:
                product.config_name = product._get_config_name()
            else:
                product.config_name = product.name

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
            # ⓘ D-368 — même exclusion que `get_cfg_price` : une variante née AVANT le
            # réglage peut encore porter la valeur d'une question vendue à part.
            apart = product.product_tmpl_id._sale_separately_attribute_ids()
            if apart:
                value_ids = value_ids.filtered(lambda v: v.attribute_id.id not in apart)
            extra_prices = attribute_value_obj.get_attribute_value_extra_prices(
                product_tmpl_id=product.product_tmpl_id.id, pt_attr_value_ids=value_ids
            )
            product.price_extra = sum(extra_prices.values())
        return result

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

    def _get_config_name(self):
        """Name for configured products
        :param: return : String"""
        self.ensure_one()
        return self.name

    def reconfigure_product(self):
        """Reconfigurer cette variante — même règle que `configure_product`."""
        return self.product_tmpl_id.configure_product()

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
            # ⚠️ Sans `env.su`, un code en `sudo` passe sur le gabarit (sa jumelle
            # `product.template.check_config_user_access` l'accepte) et bute sur la
            # variante : le visiteur public ne peut plus TERMINER sa configuration.
            or self.env.su
        ):
            return True
        raise ValidationError(
            self.env._(
                "Sorry, you are not allowed to create/change this kind of "
                "document. For more information please contact your manager."
            )
        )
