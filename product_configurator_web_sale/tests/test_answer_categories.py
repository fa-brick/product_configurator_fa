"""Les réponses qui désignent un PRODUIT se rangent sous ses catégories E-COMMERCE — D-382.

Arbitrage de Gerry (2026-09-30) : la catégorie e-commerce, traduisible, plutôt que la
catégorie de produit, interne. Ce qui est éprouvé : l'ENFANT FINAL seul, et la clé préfixée.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestShopAnswerCategories(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Public = cls.env["product.public.category"]
        cls.chassis = Public.create({"name": "Châssis D-382", "sequence": 1})
        cls.camera = Public.create({"name": "Plaque caméra", "parent_id": cls.chassis.id})
        Template = cls.env["product.template"]
        # Rangé dans « Châssis » ET dans sa descendante : seule la descendante compte.
        cls.plaque = Template.create({
            "name": "Plaque Ciné", "public_categ_ids": [Command.set((cls.chassis | cls.camera).ids)]})
        cls.bras = Template.create({
            "name": "Bras", "public_categ_ids": [Command.set(cls.chassis.ids)]})
        cls.vis = Template.create({"name": "Vis"})
        cls.attribute = cls.env["product.attribute"].create({
            # ⓘ `dynamic` : un composant « sans variante » est refusé sur un produit configurable
            # depuis W-99 / D-393 — et la catégorie d'une réponse ne dépend pas de la nature.
            "name": "Pièce", "create_variant": "dynamic", "value_type": "product",
            "display_type": "card"})
        Value = cls.env["product.attribute.value"]
        cls.values = Value.create([
            {"name": t.name, "attribute_id": cls.attribute.id, "product_id": t.product_variant_id.id}
            for t in (cls.plaque, cls.bras, cls.vis)])
        tmpl = Template.create({
            "name": "Drone configurable", "config_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id, "value_ids": [Command.set(cls.values.ids)]})],
        })
        cls.session = cls.env["product.config.session"].create(
            {"product_tmpl_id": tmpl.id, "user_id": cls.env.user.id})

    def test_l_enfant_final_seul_et_la_cle_prefixee(self):
        question = self.session.web_state()["attributes"][0]
        keys = {v["name"]: v["categoryKeys"] for v in question["values"]}
        self.assertEqual(keys["Plaque Ciné"], ["w%s" % self.camera.id])
        self.assertEqual(keys["Bras"], ["w%s" % self.chassis.id])
        self.assertEqual(keys["Vis"], [])
        self.assertEqual({c["name"] for c in question["categories"]},
                         {"Châssis D-382", "Plaque caméra"})
