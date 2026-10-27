# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models
from odoo.tools.misc import format_amount


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def web3d_optional_products(self, pricelist_id=None, date_order=None):
        """Les produits optionnels proposés sur le devis, une fois ce produit configuré — D-537.

        ⓘ Chiffrés comme le devis : sa liste de prix, sa date (hors taxes, comme ses lignes).
        ⚠️ Un optionnel à choix d'Odoo (plusieurs variantes) n'est pas proposé : l'ajouter d'ici
        poserait une variante que personne n'a choisie.
        """
        self.ensure_one()
        pricelist = self.env["product.pricelist"].browse(pricelist_id or [])
        day = fields.Datetime.to_datetime(date_order) if date_order else False
        currency = pricelist.currency_id or self.env.company.currency_id
        out = []
        for tmpl in self.optional_product_ids.filtered("sale_ok"):
            if not tmpl.config_ok and tmpl.has_configurable_attributes:
                continue
            priced = tmpl if tmpl.config_ok else tmpl.product_variant_id
            price = (pricelist._get_product_price(priced, 1.0, date=day) if pricelist
                     else priced._price_compute("list_price")[priced.id])
            out.append({
                "id": tmpl.id,
                "name": tmpl.display_name,
                "image": f"/web/image/product.template/{tmpl.id}/image_128",
                "price": format_amount(self.env, price, currency),
                "fromPrice": bool(tmpl.config_ok),
                "action": "configure" if tmpl.config_ok else "add",
                "productId": None if tmpl.config_ok else tmpl.product_variant_id.id,
                "url": None,
            })
        return out
