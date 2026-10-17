"""Les valeurs s'ouvrent dans un DIALOGUE — B5, QE, D-206.

⚠️ Au clic, une ligne ouvre la liste de ses valeurs dans un dialogue.
Un dialogue et non une action pleine page, à l'inverse du cœur : la pleine page
perd le contexte de l'arbre, qui est justement ce que l'onglet apporte.
"""

from odoo.addons.base.tests.common import BaseCommon


class ValuesDialog(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create(
            {"name": "Shade D", "create_variant": "no_variant"}
        )
        cls.values = cls.env["product.attribute.value"].create([
            {"name": f"Shade {n}", "attribute_id": cls.attribute.id} for n in range(3)
        ])
        cls.template = cls.env["product.template"].create({
            "name": "Panel D", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": cls.attribute.id,
                "value_ids": [(6, 0, cls.values.ids)],
            })],
        })
        cls.line = cls.template.attribute_line_ids

    def test_01_the_action_opens_in_a_DIALOG(self):
        action = self.line.action_open_values()
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["res_model"], "product.template.attribute.value")

    def test_02_and_shows_the_values_of_THIS_line_only(self):
        """⚠️ Le domaine porte sur la LIGNE, jamais sur l'attribut.

        Deux produits partagent un attribut mais jamais ses valeurs de produit :
        filtrer sur l'attribut montrerait celles de tout le catalogue.
        """
        autre = self.env["product.template"].create({
            "name": "Panel D bis", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": self.attribute.id,
                "value_ids": [(6, 0, self.values.ids)],
            })],
        })
        action = self.line.action_open_values()
        trouvees = self.env["product.template.attribute.value"].search(action["domain"])
        self.assertEqual(trouvees, self.line.product_template_value_ids)
        self.assertFalse(trouvees & autre.attribute_line_ids.product_template_value_ids)

    def test_03_a_DEACTIVATED_value_stays_visible_there(self):
        """⚠️ Sans `active_test=False`, on ne verrait pas ce qu'on vient chercher.

        Une valeur désactivée (D-205) est précisément celle dont on veut
        comprendre le sort — et le dialogue est le seul endroit d'où la
        réactiver. Le filtre par défaut d'Odoo l'aurait masquée.
        """
        ptav = self.line.product_template_value_ids[0]
        ptav.ptav_active = False
        action = self.line.action_open_values()
        self.assertEqual(action["context"].get("active_test"), False)
        trouvees = self.env["product.template.attribute.value"].with_context(
            **action["context"]
        ).search(action["domain"])
        self.assertIn(ptav, trouvees)
