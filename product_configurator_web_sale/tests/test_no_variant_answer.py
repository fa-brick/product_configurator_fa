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
        """Une configuration CONFIRMÉE, comme la page la confirme (`action_confirm` écrit
        l'article sur la session — c'est par lui que le panier reconnaît son jeton)."""
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
            "value_ids": [Command.set([v.id for v in values])],
        })
        session.action_confirm()
        return session, session.product_id

    def _to_cart(self, variant, ptav_ids, session=None, order=None):
        """Ce que fait la page : la variante, ses réponses « sans variante », et — depuis W-99 —
        le JETON de sa configuration (`config_session_token`)."""
        order = order or self.empty_cart
        token = None
        if session:
            session._ensure_access_token()
            token = session.access_token
        result = order._cart_update(product_id=variant.id, add_qty=1,
                                    no_variant_attribute_value_ids=ptav_ids,
                                    config_session_token=token)
        return order.order_line.browse(result["line_id"])

    def _page_ptav_ids(self, session):
        return session._web_no_variant_ptav_ids()

    def test_01_la_ligne_porte_la_reponse_choisie_pas_la_premiere(self):
        session, variant = self._configure(self.classic, self.gloss)
        line = self._to_cart(variant, self._page_ptav_ids(session))
        chosen = line.product_no_variant_attribute_value_ids.product_attribute_value_id
        self.assertEqual(chosen, self.gloss, "la finition choisie (Brillant) doit être sur la ligne")
        self.assertIn("Brillant", line.name)
        self.assertNotIn("Mat", line.name.replace("Brillant", ""))

    def test_02_la_ligne_garde_l_article_configure(self):
        """W-99 / D-393 (option A) — le défaut constaté le 2026-10-01 est CORRIGÉ : la réponse
        « sans variante » ne fait plus partie de l'article, le panier n'a donc plus d'article
        à recomposer. Ce test remplace le test de caractérisation `test_02_DEFAUT_CONNU_…`."""
        session, variant = self._configure(self.cine, self.gloss)
        line = self._to_cart(variant, self._page_ptav_ids(session))
        names = lambda p: set(p.product_template_attribute_value_ids
                              .product_attribute_value_id.mapped("name"))
        self.assertEqual(names(variant), {"Cine"})          # la finition n'est plus dans l'article
        self.assertEqual(line.product_id, variant)

    # ── W-99 lot 2 : la ligne LIÉE à sa configuration (Q2) ──────────────────────────────────
    def test_03_la_ligne_porte_sa_configuration_ses_reponses_et_son_prix(self):
        session, variant = self._configure(self.cine, self.gloss)
        line = self._to_cart(variant, self._page_ptav_ids(session), session=session)
        self.assertEqual(line.config_session_id, session)
        self.assertEqual(line.product_id, variant)
        self.assertEqual(line.product_no_variant_attribute_value_ids.product_attribute_value_id,
                         self.gloss)
        self.assertEqual(line.price_unit, session.price)

    def test_04_meme_si_la_page_n_envoie_RIEN_la_session_dit_les_reponses(self):
        """Le jeton suffit : la ligne relit les réponses dans la configuration elle-même."""
        session, variant = self._configure(self.cine, self.gloss)
        line = self._to_cart(variant, [], session=session)
        self.assertEqual(line.product_no_variant_attribute_value_ids.product_attribute_value_id,
                         self.gloss)

    def test_05_une_configuration_une_ligne(self):
        """Deux configurations qui ne diffèrent que par une réponse « sans variante » : le MÊME
        article, mais DEUX lignes. La même configuration ajoutée deux fois : une ligne, 2."""
        order = self.empty_cart
        s1, v1 = self._configure(self.cine, self.gloss)
        s2, v2 = self._configure(self.cine, self.matte)
        self.assertEqual(v1, v2)
        l1 = self._to_cart(v1, [], session=s1, order=order)
        l2 = self._to_cart(v2, [], session=s2, order=order)
        self.assertNotEqual(l1, l2)
        again = self._to_cart(v1, [], session=s1, order=order)
        self.assertEqual(again, l1)
        self.assertEqual(l1.product_uom_qty, 2)

    def test_06_un_jeton_d_une_AUTRE_configuration_ne_lie_rien(self):
        """Le jeton ne vaut que pour l'article que SA configuration a fait naître."""
        s1, v1 = self._configure(self.cine, self.gloss)
        s2, v2 = self._configure(self.classic, self.gloss)
        line = self._to_cart(v1, [], session=s2)
        self.assertFalse(line.config_session_id)

