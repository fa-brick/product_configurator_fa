"""Une question VENDUE À PART — D-368 (option B de Gerry).

Le cas : le bumper avant d'un drone, en option. Sa réponse ne fait ni le prix, ni la
variante, ni donc la nomenclature du drone : le bumper aura sa propre ligne de devis.
"""
from odoo import Command
from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon


class SaleSeparately(BaseCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.bumper_product = cls.env["product.product"].create(
            {"name": "Bumper Ciné", "list_price": 15.0, "sale_ok": True})
        cls.plate = Attribute.create({"name": "Cam plate", "create_variant": "dynamic"})
        cls.classic, cls.cine = Value.create([
            {"name": "Classic", "attribute_id": cls.plate.id},
            {"name": "Ciné", "attribute_id": cls.plate.id},
        ])
        cls.bumper = Attribute.create({"name": "Bumper avant", "create_variant": "no_variant",
                                       "value_type": "product"})
        cls.none, cls.with_bumper = Value.create([
            {"name": "Sans bumper", "attribute_id": cls.bumper.id},
            {"name": "Bumper Ciné", "attribute_id": cls.bumper.id,
             "product_id": cls.bumper_product.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Drone", "config_ok": True, "list_price": 100.0,
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.plate.id,
                                "value_ids": [Command.set((cls.classic | cls.cine).ids)]}),
                Command.create({"attribute_id": cls.bumper.id, "required": False,
                                "value_ids": [Command.set((cls.none | cls.with_bumper).ids)]}),
            ],
        })
        cls.line = cls.tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id == cls.bumper)

    def _session(self, *values):
        return self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
            "value_ids": [Command.set([v.id for v in values])],
        })

    # ── les gardes ──────────────────────────────────────────────────────────
    def test_une_question_qui_cree_des_variantes_ne_se_vend_pas_a_part(self):
        motor = self.env["product.attribute"].create(
            {"name": "Moteur", "create_variant": "dynamic", "value_type": "product"})
        line = self.env["product.template.attribute.line"].create({
            "product_tmpl_id": self.tmpl.id, "attribute_id": motor.id,
            "value_ids": [Command.create({"name": "M1", "attribute_id": motor.id})],
        })
        with self.assertRaisesRegex(ValidationError, "creates variants"):
            line.sale_separately = True

    def test_une_question_sans_produit_ne_se_vend_pas_a_part(self):
        text = self.env["product.attribute"].create(
            {"name": "Gravure", "create_variant": "no_variant", "value_type": "value"})
        line = self.env["product.template.attribute.line"].create({
            "product_tmpl_id": self.tmpl.id, "attribute_id": text.id,
            "value_ids": [Command.create({"name": "Oui", "attribute_id": text.id})],
        })
        with self.assertRaisesRegex(ValidationError, "designate products"):
            line.sale_separately = True

    # ── le prix ─────────────────────────────────────────────────────────────
    def test_integree_la_piece_fait_le_prix_du_produit(self):
        """Ce qui existait : une valeur qui désigne un produit ajoute son prix."""
        self.assertEqual(self._session(self.classic, self.with_bumper).get_cfg_price(), 115.0)

    def test_vendue_a_part_elle_ne_le_fait_plus(self):
        self.line.sale_separately = True
        self.assertEqual(self._session(self.classic, self.with_bumper).get_cfg_price(), 100.0)

    # ── la variante ─────────────────────────────────────────────────────────
    def test_vendue_a_part_elle_n_entre_pas_dans_la_variante(self):
        """Deux drones aux bumpers différents sont le MÊME drone — et la nomenclature, que
        `_fa_mrp` bâtit sur les valeurs de la variante, ne porte pas le bumper."""
        self.line.sale_separately = True
        sans = self._session(self.classic, self.none).create_get_variant()
        avec = self._session(self.classic, self.with_bumper).create_get_variant()
        self.assertEqual(sans, avec)
        self.assertEqual(avec.product_template_attribute_value_ids.product_attribute_value_id,
                         self.classic)
        self.assertEqual(avec.price_extra, 0.0)

    # ── ce qui se voit ──────────────────────────────────────────────────────
    def test_l_arbre_du_configurateur_le_dit(self):
        self.line.sale_separately = True
        row = next(r for r in self.tmpl.get_configurator_tree()
                   if r["kind"] == "attribute" and r["id"] == self.line.id)
        self.assertTrue(row["sale_separately"])

    def test_un_produit_qui_ne_se_vend_pas_est_signale(self):
        self.line.sale_separately = True
        self.assertFalse(self.line.sale_separately_warning)
        self.bumper_product.sale_ok = False
        self.line.invalidate_recordset(["sale_separately_warning"])
        self.assertIn("Bumper Ciné", self.line.sale_separately_warning)
