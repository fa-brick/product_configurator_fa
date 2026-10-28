"""Ce qu'exécute `product.template.attribute.value` (BLL, D-541)."""
from odoo import api, models


class ProductAttributePrice(models.Model):
    _inherit = "product.template.attribute.value"

    @api.depends("ptav_product_variant_ids")
    def _compute_removal_effect(self):
        for value in self:
            value.removal_effect = (
                "archive" if value._removal_would_archive() else "delete"
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Le taux du CATALOGUE devient celui du produit, sauf mention contraire.

        Odoo fait déjà ce geste pour `price_extra`
        (`product_template_attribute_line.py:244`) mais ne connaît pas notre
        taux : sans cette recopie, la valeur créée pour un produit repartirait à
        zéro et le nuancier ne servirait de défaut à rien (D-162).
        """
        for vals in vals_list:
            if "price_extra_sqm" in vals or not vals.get("product_attribute_value_id"):
                continue
            value = self.env["product.attribute.value"].browse(
                vals["product_attribute_value_id"]
            )
            if value.default_extra_price_sqm:
                vals["price_extra_sqm"] = value.default_extra_price_sqm
        return super().create(vals_list)

    def _removal_would_archive(self):
        """Une variante empêche-t-elle la suppression ?

        ⓘ `_filter_to_unlink` est le point d'extension où `sale` écarte les
        variantes liées à une ligne de commande, et `stock` celles qui ont un
        mouvement. L'interroger est la seule réponse vraie : la recopier ici
        divergerait au premier module installé.

        ⚠️ **APPELÉ SANS ARGUMENT, et ce n'est pas un détail.** Le cœur déclare
        `_filter_to_unlink(self, check_access=True)`, mais `stock` le surcharge en
        `_filter_to_unlink(self)` — sans le paramètre. Passer `check_access` lève
        donc un `TypeError` dès que `stock` est installé, c'est-à-dire presque
        partout. Le cœur lui-même l'appelle sans argument (`_unlink_or_archive`) :
        c'est la seule forme que toute la chaîne accepte.
        """
        self.ensure_one()
        variants = self.ptav_product_variant_ids
        if not variants:
            return False
        return bool(variants - variants._filter_to_unlink())
