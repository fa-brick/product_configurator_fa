"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
from odoo import api, models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    @api.depends(
        "value_ids",
        "product_tmpl_id.list_price",
        "product_tmpl_id.attribute_line_ids",
        "product_tmpl_id.attribute_line_ids.value_ids",
        "product_tmpl_id.attribute_line_ids.product_template_value_ids",
        "product_tmpl_id.attribute_line_ids." "product_template_value_ids.price_extra",
        # ⚠️ **LES SAISIES AUSSI** (D-353). Une largeur TAPÉE n'entrait ni dans le
        # calcul ni dans ses dépendances : la grille voyait « pas de largeur »,
        # affichait le prix de départ, et la ligne de devis partait à ce prix.
        "custom_value_ids",
        "custom_value_ids.value",
    )
    def _compute_cfg_price(self):
        for session in self:
            if session.product_tmpl_id:
                price = session.get_cfg_price(
                    custom_vals=session._get_custom_vals_dict()
                )
            else:
                price = 0.00
            session.price = price

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

    @api.model
    def get_cfg_price(self, value_ids=None, custom_vals=None, pricelist=None, date=None):
        """Computes the price of the configured product based on the
            configuration passed in via value_ids and custom_values

        :param value_ids: list of attribute value_ids
        :param custom_vals: dictionary of custom attribute values
        :param date: the day whose grid and pricelist rules apply — today when empty
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
        # ⚠️ **UNE QUESTION VENDUE À PART N'ENTRE PAS DANS LE PRIX** (D-368) : sa pièce a sa
        # propre ligne de devis, la compter ici la ferait payer deux fois (D-106). Filtré
        # dans les deux TOTAUX — celui-ci et `_compute_product_price_extra` — et non dans
        # `get_attribute_value_extra_prices`, qui sert aussi à AFFICHER le prix d'une valeur.
        apart = product_tmpl._sale_separately_attribute_ids()
        if apart:
            av_ids = av_ids.filtered(lambda v: v.attribute_id.id not in apart)
        extra_prices = attr_val_obj.get_attribute_value_extra_prices(
            product_tmpl_id=product_tmpl.id, pt_attr_value_ids=av_ids
        )
        price_extra = sum(extra_prices.values())
        # Le prix d'un produit DIMENSIONNÉ vient de sa grille, pas du
        # `list_price` du template — lequel n'est qu'un « à partir de » (D-083,
        # D-093). Faute de grille, on retombe sur le comportement d'OCA : le
        # produit n'est pas dimensionné, ou son absence de grille a déjà été
        # signalée à l'arrivée dans la fiche.
        base_price = self._get_config_grid_price(value_ids, custom_vals, date=date)
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
        return pricelist._get_product_price(template, 1.0, date=date)

    def _get_order_price(self, order):
        """Le prix de cette configuration sur UNE commande.

        ⚠️ La liste de prix et la date de la COMMANDE, pas celles de qui calcule : sinon un
        devis serait chiffré à la liste du commercial et à la grille du jour (D-537).
        """
        self.ensure_one()
        return self.get_cfg_price(
            custom_vals=self._get_custom_vals_dict(),
            pricelist=order.pricelist_id,
            date=order.date_order,
        )

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

    def _get_config_grid_price(self, value_ids=None, custom_vals=None, date=None):
        """Le prix de grille de la configuration courante, ou `None`."""
        self.ensure_one()
        grid = self.product_tmpl_id._get_price_grid(date=date)
        if not grid:
            return None
        dimensions = self._get_config_dimensions(value_ids, custom_vals)
        if "axis_x" not in dimensions or "axis_y" not in dimensions:
            return None
        return grid.get_price(dimensions["axis_x"], dimensions["axis_y"])

    def _is_out_of_grid(self, value_ids=None, custom_vals=None, date=None):
        """Les deux cotes sont connues, une grille existe, et aucune case n'y répond.

        ⚠️ Une cote MANQUANTE n'est pas hors grille : la configuration est seulement
        incomplète, et la bloquer fermerait le panier avant la première réponse (D-537).
        """
        self.ensure_one()
        grid = self.product_tmpl_id._get_price_grid(date=date)
        if not grid:
            return False
        if value_ids is None:
            value_ids = self.value_ids.ids
        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()
        dimensions = self._get_config_dimensions(value_ids, custom_vals)
        if "axis_x" not in dimensions or "axis_y" not in dimensions:
            return False
        return grid.get_price(dimensions["axis_x"], dimensions["axis_y"]) is None

    def _out_of_grid_message(self, date=None):
        """Ce que la page dit d'une configuration hors grille, ou `None` (D-537).

        ⓘ Les BORNES de la grille quand une cote les dépasse : le client sait alors quoi changer.
        """
        self.ensure_one()
        if not self._is_out_of_grid(date=date):
            return None
        grid = self.product_tmpl_id._get_price_grid(date=date)
        lines = self.product_tmpl_id._grid_axis_lines()
        dimensions = self._get_config_dimensions(
            self.value_ids.ids, self._get_custom_vals_dict())
        bounds = {}
        for role, brackets in (("axis_x", grid.axis_x_bracket_ids),
                               ("axis_y", grid.axis_y_bracket_ids)):
            top = max(brackets.mapped("max_value"), default=0.0)
            if dimensions[role] <= top:
                continue
            unit = lines[role].attribute_id.uom_id.name or ""
            bounds[role] = f"{top:g} {unit}".strip()
        if not bounds:
            return self.env._("These dimensions have no price in the price grid.")
        return self.env._(
            "No price for these dimensions in the price grid (%(limits)s).",
            limits=", ".join(
                self.env._("%(dimension)s: %(bound)s maximum",
                           dimension=lines[role].attribute_id.name, bound=bound)
                for role, bound in bounds.items()),
        )

    def get_config_surface(self, value_ids=None, custom_vals=None):
        """La surface en m² de la configuration courante, ou 0 — D-161.

        Point d'appel PUBLIC : l'étiquette de prix de la page s'en sert, pour afficher
        aux valeurs au mètre carré leur MONTANT plutôt que leur taux (D-162).

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
