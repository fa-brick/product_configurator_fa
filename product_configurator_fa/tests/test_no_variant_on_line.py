"""Une réponse « sans variante » va sur la LIGNE, plus dans l'article — W-99 / D-393 (option A).

Le cas : une finition (« Mat », « Brillant ») qui ne change pas l'article, et une plaque
(« Classic », « Ciné ») qui le change.
"""
from odoo import Command
from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon


class NoVariantOnLine(BaseCommon):

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
            "name": "Drone", "config_ok": True, "list_price": 100.0,
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.plate.id,
                                "value_ids": [Command.set((cls.classic | cls.cine).ids)]}),
                Command.create({"attribute_id": cls.finish.id,
                                "value_ids": [Command.set((cls.matte | cls.gloss).ids)]}),
            ],
        })
        # Un COMPOSANT : des valeurs qui désignent des produits.
        cls.motor_product = cls.env["product.product"].create({"name": "Moteur M1"})
        cls.motor = Attribute.create({"name": "Moteur", "create_variant": "no_variant",
                                      "value_type": "product"})
        cls.m1 = Value.create({"name": "M1", "attribute_id": cls.motor.id,
                               "product_id": cls.motor_product.id})

    def _variant(self, *values):
        return self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
            "value_ids": [Command.set([v.id for v in values])],
        }).create_get_variant()

    # ── l'article ───────────────────────────────────────────────────────────────────────────
    def test_01_la_reponse_sans_variante_n_entre_pas_dans_l_article(self):
        variant = self._variant(self.cine, self.gloss)
        self.assertEqual(variant.product_template_attribute_value_ids.product_attribute_value_id,
                         self.cine)

    def test_02_deux_configurations_qui_ne_different_que_par_elle_sont_le_meme_article(self):
        self.assertEqual(self._variant(self.cine, self.gloss), self._variant(self.cine, self.matte))

    def test_03_une_question_qui_cree_des_variantes_les_cree_toujours(self):
        self.assertNotEqual(self._variant(self.cine, self.gloss), self._variant(self.classic, self.gloss))

    # ── ce qu'une question « sans variante » ne peut pas être sur un produit configurable ──
    def _add_line(self, tmpl, attribute, values, **extra):
        return self.env["product.template.attribute.line"].create({
            "product_tmpl_id": tmpl.id, "attribute_id": attribute.id,
            "value_ids": [Command.set(values.ids)], **extra})

    def test_04_un_composant_integre_est_refuse(self):
        with self.assertRaisesRegex(ValidationError, "designates components"):
            self._add_line(self.tmpl, self.motor, self.m1)

    def test_05_vendu_a_part_il_est_accepte(self):
        line = self._add_line(self.tmpl, self.motor, self.m1, sale_separately=True)
        self.assertTrue(line.sale_separately)

    def test_06_sur_un_produit_ORDINAIRE_rien_ne_change(self):
        plain = self.env["product.template"].create({"name": "Ordinaire"})
        self.assertTrue(self._add_line(plain, self.motor, self.m1))

    def test_07_rendre_configurable_un_produit_qui_en_porte_un_est_refuse(self):
        plain = self.env["product.template"].create({"name": "Ordinaire"})
        self._add_line(plain, self.motor, self.m1)
        with self.assertRaisesRegex(ValidationError, "designates components"):
            plain.config_ok = True

    def test_08_un_axe_de_grille_sans_variante_est_refuse(self):
        """Seul un attribut NUMÉRIQUE porte un axe (règle existante) : on en prend un, sans
        variante — c'est lui que D-393 refuse."""
        width = self.env["product.attribute"].create({
            "name": "Largeur sans variante", "val_custom": True, "custom_type": "float",
            "create_variant": "no_variant"})
        with self.assertRaisesRegex(ValidationError, "price grid axis"):
            self._add_line(self.tmpl, width, self.env["product.attribute.value"],
                           dimension_role="axis_x")
