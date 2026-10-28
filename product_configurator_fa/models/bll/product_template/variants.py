"""Ce qu'exécute `product.template` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import UserError


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

    def _sale_separately_attribute_ids(self):
        """Les questions de ce produit VENDUES À PART — `set` d'identifiants (D-368).

        ⓘ Le seul lecteur du réglage côté produit : le prix, la variante et la page le
        demandent ici, plutôt que de refiltrer les lignes chacun à sa façon.
        """
        return set(self.attribute_line_ids.filtered("sale_separately").attribute_id.ids)

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

    def configure_product(self):
        """Configurer ce produit — la page vient de `product_configurator_web_3d`.

        ⚠️ Le NOM reste ici : les boutons des vues de ce module l'appellent, et une vue qui
        cite une méthode absente ne s'installe plus ([[L-166]]).
        ⓘ Sans la page 3D, il n'existe aucune interface de configuration (D-097, D-497).
        """
        raise UserError(self.env._(
            "Configuring a product requires the 3D configurator page "
            "(module product_configurator_web_3d)."
        ))
