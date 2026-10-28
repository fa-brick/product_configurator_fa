"""Ce qu'exécute `product.template` (BLL, D-541)."""
# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models
from odoo.tools.misc import format_amount


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _website_show_quick_add(self):
        """Pas d'ajout RAPIDE pour ce qui doit d'abord être configuré.

        ⚠️ Ce verrou est en Python, pas dans le gabarit, et c'est délibéré : le
        bouton d'ajout rapide de la vignette vit dans une vue OPTIONNELLE
        (`website_sale.products_add_to_cart`, `active=False` d'origine). Un
        `xpath` sur son contenu casserait tant qu'elle est éteinte, et ne
        protégerait rien tant qu'elle l'est. La méthode, elle, est appelée par
        cette vue quel que soit son état.
        """
        self.ensure_one()
        if self.config_ok:
            return False
        return super()._website_show_quick_add()

    def _get_sales_prices(self, website):
        """Le prix de la vignette d'un produit configurable = celui de sa fiche.

        ⚠️ Laisser le calcul d'Odoo, c'est annoncer le seul `list_price` du modèle, sans le prix
        des composants : la liste afficherait un montant qu'aucune configuration n'atteint (D-536).
        ⓘ Même calcul que la fiche (`_get_combination_info`, combinaison par défaut).
        """
        res = super()._get_sales_prices(website)
        for template in self.filtered("config_ok"):
            info = template._get_combination_info()
            vals = {"price_reduce": info["price"]}
            if info["has_discounted_price"]:
                vals["base_price"] = info["list_price"]
            elif info["compare_list_price"]:
                vals["base_price"] = info["compare_list_price"]
            res[template.id] = vals
        return res

    def _get_possible_variants_sorted(self, parent_combination=None):
        """Pas de LISTE des variantes sur la fiche d'un produit configurable — W-69.

        ⚠️ **Le second chemin des questions, et il ne passe pas par les sélecteurs.** Le mode
        « Liste des variantes » de la boutique (`website_sale.product_variants`, actif sur
        fabk18) REMPLACE le bloc des sélecteurs par des boutons radio : un par variante
        existante. Pour un produit configurable, ce sont les configurations PASSÉES des autres
        clients — proposées à l'achat, sans configurateur (relevé le 2026-10-01). La règle qui
        masque les sélecteurs ne le voit pas : ce gabarit est éteint par défaut, un `xpath`
        sur lui casserait tant qu'il l'est. Cette méthode n'est lue que par lui.
        """
        if self.config_ok:
            return self.env["product.product"]
        return super()._get_possible_variants_sorted(parent_combination=parent_combination)

    def _web_optional_products(self, website):
        """Les produits optionnels à proposer une fois ce produit configuré mis au panier — D-537.

        ⚠️ Seuls ceux que le visiteur peut ACHETER : publiés, vendables, de ce site. Un optionnel
        invisible ouvrirait sur une page 403 ou un bouton refusé.
        ⓘ Un optionnel configurable se CONFIGURE ; un optionnel qui a des choix d'Odoo s'ouvre sur sa
        fiche ; les autres s'ajoutent, rattachés à la ligne du produit.
        """
        self.ensure_one()
        options = self.optional_product_ids.filtered(
            lambda tmpl: tmpl.sale_ok and tmpl.website_published
            and tmpl.website_id in (website, website.browse())
        )
        prices = options._get_sales_prices(website)
        out = []
        for tmpl in options:
            if tmpl.config_ok:
                action, product_id, url = (
                    "configure", None,
                    f"/configurator/start/{self.env['ir.http']._slug(tmpl)}")
            elif tmpl.has_configurable_attributes or not tmpl._is_add_to_cart_possible():
                action, product_id, url = "view", None, tmpl.website_url
            else:
                action, product_id, url = "add", tmpl._get_first_possible_variant_id(), None
            out.append({
                "id": tmpl.id,
                "name": tmpl.display_name,
                "image": f"/web/image/product.template/{tmpl.id}/image_128",
                "price": format_amount(self.env, prices[tmpl.id]["price_reduce"],
                                       website.currency_id),
                # ⓘ Un optionnel configurable n'a qu'un prix de départ, comme sur sa vignette (D-536).
                "fromPrice": bool(tmpl.config_ok),
                "action": action,
                "productId": product_id,
                "url": url,
            })
        return out
