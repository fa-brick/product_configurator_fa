"""À la bascule en configurable, on PRÉVIENT — D-200 (QB).

⚠️ Ces exclusions sont déjà sans effet : le configurateur ne les lit pas, et
`_create_variant_ids` saute les produits configurables, ce qui prive les
exclusions de leur seul autre consommateur. L'avertissement ne change donc aucun
comportement — **il rend explicite un silence**.
"""

from odoo.addons.base.tests.common import BaseCommon


class ExclusionWarning(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create(
            {"name": "Finish QB", "create_variant": "always"}
        )
        cls.value_a, cls.value_b = cls.env["product.attribute.value"].create([
            {"name": "Matt", "attribute_id": cls.attribute.id},
            {"name": "Gloss", "attribute_id": cls.attribute.id},
        ])
        cls.template = cls.env["product.template"].create({
            "name": "Panel QB",
            "attribute_line_ids": [(0, 0, {
                "attribute_id": cls.attribute.id,
                "value_ids": [(6, 0, (cls.value_a + cls.value_b).ids)],
            })],
        })

    def _ptav(self, value):
        return self.template.attribute_line_ids.product_template_value_ids.filtered(
            lambda p, v=value: p.product_attribute_value_id == v
        )

    def test_01_a_product_WITHOUT_exclusions_says_nothing(self):
        """⚠️ Le cas le plus fréquent : avertir toujours serait un bruit."""
        self.template.config_ok = True
        self.assertFalse(self.template._onchange_config_ok_warns_about_exclusions())

    def test_02_a_product_that_CARRIES_exclusions_warns(self):
        self.env["product.template.attribute.exclusion"].create({
            "product_tmpl_id": self.template.id,
            "product_template_attribute_value_id": self._ptav(self.value_a).id,
            "value_ids": [(6, 0, self._ptav(self.value_b).ids)],
        })
        self.template.config_ok = True
        avertissement = self.template._onchange_config_ok_warns_about_exclusions()
        self.assertTrue(avertissement, "aucun avertissement sur un produit qui en porte")
        self.assertIn("warning", avertissement)

    def test_03_and_says_NOTHING_when_the_product_stops_being_configurable(self):
        """L'avertissement porte sur la bascule VERS le configurable, pas l'inverse.

        ⚠️ Un `onchange` se déclenche dans les deux sens : sans ce garde-fou, on
        avertirait aussi celui qui REND un produit ordinaire — au moment précis où
        ses exclusions redeviennent utiles.
        """
        self.env["product.template.attribute.exclusion"].create({
            "product_tmpl_id": self.template.id,
            "product_template_attribute_value_id": self._ptav(self.value_a).id,
            "value_ids": [(6, 0, self._ptav(self.value_b).ids)],
        })
        self.template.config_ok = False
        self.assertFalse(self.template._onchange_config_ok_warns_about_exclusions())

    def test_04_NOTHING_is_deleted_nor_converted(self):
        """Ni conversion ni refus : « un avertissement », et rien d'autre."""
        exclusion = self.env["product.template.attribute.exclusion"].create({
            "product_tmpl_id": self.template.id,
            "product_template_attribute_value_id": self._ptav(self.value_a).id,
            "value_ids": [(6, 0, self._ptav(self.value_b).ids)],
        })
        self.template.config_ok = True
        self.template._onchange_config_ok_warns_about_exclusions()
        self.assertTrue(exclusion.exists())
        self.assertTrue(self.template.config_ok, "la bascule n'est pas refusée")
