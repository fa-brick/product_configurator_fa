# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Q7 de W-69 — la réponse à une question « sans variante » survit-elle jusqu'au panier ?

Le chemin de la page : la session est confirmée (`create_get_variant`), puis la VARIANTE va
au panier par `/shop/cart/update_json`, avec les seules réponses des questions vendues à
part (`noVariantPtavIds`, D-368). Ce test rejoue exactement cela, sans navigateur.
"""
from odoo import Command

from odoo.addons.website_sale.tests.common import WebsiteSaleCommon


class NoVariantAnswerInCart(WebsiteSaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.plate = Attribute.create({"name": "Plaque", "create_variant": "dynamic"})
        cls.classic, cls.cine = Value.create([
            {"name": "Classic", "attribute_id": cls.plate.id},
            {"name": "Cine", "attribute_id": cls.plate.id},
        ])
        cls.finish = Attribute.create({"name": "Finition", "create_variant": "no_variant"})
        cls.matte, cls.gloss = Value.create([
            {"name": "Mat", "attribute_id": cls.finish.id},
            {"name": "Brillant", "attribute_id": cls.finish.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Drone W69", "config_ok": True, "list_price": 100.0, "is_published": True,
            "website_published": True, "sale_ok": True,
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.plate.id,
                                "value_ids": [Command.set((cls.classic | cls.cine).ids)]}),
                Command.create({"attribute_id": cls.finish.id,
                                "value_ids": [Command.set((cls.matte | cls.gloss).ids)]}),
            ],
        })

    def _configure(self, *values):
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
            "value_ids": [Command.set([v.id for v in values])],
        })
        return session, session.create_get_variant()

    def _to_cart(self, variant, ptav_ids):
        """Ce que fait la page : la variante, et les réponses qu'elle sait transmettre."""
        order = self.empty_cart
        result = order._cart_update(product_id=variant.id, add_qty=1,
                                    no_variant_attribute_value_ids=ptav_ids)
        return order.order_line.browse(result["line_id"])

    def _page_ptav_ids(self, session):
        return session._web_sold_separately_ptav_ids()

    def test_01_la_ligne_porte_la_reponse_choisie_pas_la_premiere(self):
        session, variant = self._configure(self.classic, self.gloss)
        line = self._to_cart(variant, self._page_ptav_ids(session))
        chosen = line.product_no_variant_attribute_value_ids.product_attribute_value_id
        self.assertEqual(chosen, self.gloss, "la finition choisie (Brillant) doit être sur la ligne")
        self.assertIn("Brillant", line.name)
        self.assertNotIn("Mat", line.name.replace("Brillant", ""))

    def test_02_DEFAUT_CONNU_le_panier_remplace_la_variante_configuree(self):
        """⚠️ **Constat du 2026-10-01 (W-69, Q7) — un DÉFAUT, décrit tel qu'il est.**

        Le chemin hérité d'OCA fait entrer la réponse « sans variante » DANS la variante
        configurée (`Brillant, Cine`) ; le panier d'Odoo, lui, recompose la combinaison et
        crée ou retrouve la variante SANS elle (`Cine`). La ligne porte donc la bonne
        réponse (test 01), mais pas l'article que la configuration a fait naître — ni ce que
        `_fa_mrp` a bâti sur lui. Correction à arbitrer avec Gerry.

        ⓘ Ce test ÉCHOUERA le jour où le défaut sera corrigé : il faudra alors l'inverser
        (`assertEqual(line.product_id, variant)`).
        """
        session, variant = self._configure(self.cine, self.gloss)
        line = self._to_cart(variant, self._page_ptav_ids(session))
        names = lambda p: set(p.product_template_attribute_value_ids
                              .product_attribute_value_id.mapped("name"))
        self.assertEqual(names(variant), {"Cine", "Brillant"})
        self.assertNotEqual(line.product_id, variant)
        self.assertEqual(names(line.product_id), {"Cine"})
