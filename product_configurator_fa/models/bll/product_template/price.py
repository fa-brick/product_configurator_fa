"""Ce qu'exécute `product.template` (BLL, D-541)."""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.depends("price_grid_ids", "price_grid_ids.active")
    def _compute_price_grid_count(self):
        for template in self:
            template.price_grid_count = len(template.price_grid_ids)

    def action_open_price_grids(self):
        """Les grilles de CE produit.

        ⚠️ `views` explicite : cette action part vers un bouton de vue, donc elle
        serait complétée — mais la laisser incomplète ferait dépendre son bon
        fonctionnement du chemin emprunté ([[L-165]]). On l'écrit autosuffisante.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Price grids"),
            "res_model": "product.price.grid",
            "view_mode": "list,form",
            "views": [
                (self.env.ref(
                    "product_configurator_fa.product_price_grid_list_view").id, "list"),
                (self.env.ref(
                    "product_configurator_fa.product_price_grid_form_view").id, "form"),
            ],
            "domain": [("product_tmpl_id", "=", self.id)],
            "context": {"default_product_tmpl_id": self.id},
        }

    def _price_compute(
        self, price_type, uom=None, currency=None, company=None, date=False
    ):
        """Le prix d'une configuration EN COURS, avant qu'aucune variante n'existe.

        ⚠️ Rien n'est créé avant le devis (D-082) : il n'y a donc pas de
        `product.product` à qui demander un prix pendant la configuration. Le
        prix de grille entre par le CONTEXTE, et tout le reste — pourcentages,
        formules, devise, arrondis, cascades de listes de prix — continue de
        marcher sans qu'on y touche, parce qu'on emprunte le chemin d'Odoo au
        lieu d'en refaire un (D-092).

        Le contexte porte un DICTIONNAIRE par template, et non un montant :
        `_price_compute` peut recevoir plusieurs enregistrements, et une valeur
        unique se serait appliquée à tous.

        source : addons/product/models/product_template.py:688 — voir P17 du
        registre des points de contact.
        """
        prices = super()._price_compute(
            price_type, uom=uom, currency=currency, company=company, date=date
        )
        base_prices = self.env.context.get("configurator_base_prices") or {}
        if price_type != "list_price" or not base_prices:
            return prices
        company = company or self.env.company
        date = date or fields.Date.context_today(self)
        for template in self.with_company(company):
            if template.id not in base_prices:
                continue
            price = base_prices[template.id] + template._get_attributes_extra_price()
            if uom:
                price = template.uom_id._compute_price(price, uom)
            if currency:
                price = template.currency_id._convert(price, currency, company, date)
            prices[template.id] = price
        return prices

    # ⚠️ PAS de bandeau « pas de grille » : sans grille, `_get_config_grid_price` rend
    # `None` et l'appelant retombe sur le `list_price` du modèle — configurer sans
    # grille est licite (D-215).
    def _get_price_grid(self, date=None):
        """La grille en vigueur à cette date — au plus une (D-083)."""
        self.ensure_one()
        # ⚠️ Odoo passe la date tantôt en `date`, tantôt en chaîne (un contexte,
        # une valeur de devis) : comparer sans convertir lève un TypeError que
        # rien n'annonce à la lecture.
        date = fields.Date.to_date(date) or fields.Date.context_today(self)
        # ⚠️ `sudo` — SANS LUI, LA BOUTIQUE RÉPOND 403 À TOUT VISITEUR ANONYME.
        # `_price_compute` passe ici pour n'importe quel lecteur d'un prix, et
        # l'utilisateur PUBLIC n'a aucune ACL sur `product.price.grid` : les
        # droits posés en D-093 s'arrêtent au portail, parce qu'il n'y avait pas
        # de site quand ils ont été écrits. Le rendu de `website_sale.product`
        # levait donc un `AccessError` sur le premier produit venu — configurable
        # ou non.
        # ⓘ `sudo` plutôt qu'une ACL publique : ce que le visiteur doit obtenir
        # est le PRIX, pas la grille. Une ligne d'ACL rendrait les paliers et
        # les cellules lisibles partout ; ici la lecture reste enfermée dans le
        # calcul, et le `sudo` porte aussi les paliers et cellules que
        # `get_price` traverse ensuite.
        grids = self.sudo().price_grid_ids.filtered(
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
