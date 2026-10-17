from odoo.addons.base.tests.common import BaseCommon


class ThreeDColumn(BaseCommon):
    """La « Vue 3d » que l'arbre affiche — B3, D-210.

    ⚠️ Cette garde vit dans le PONT : le champ vient d'ici, et le cœur ne le
    connaît pas — l'y exposer ferait dépendre l'AGPL-3 de l'éditeur (D-075). Le
    cœur ne connaît qu'un CROCHET, que ce module remplit.
    """

    def test_01_the_hook_gives_the_camera_name(self):
        camera_model = self.env["product.model3d.camera"]
        attribute = self.env["product.attribute"].create(
            {"name": "Lock 3D", "create_variant": "no_variant"}
        )
        self.env["product.attribute.value"].create(
            {"name": "Standard", "attribute_id": attribute.id}
        )
        template = self.env["product.template"].create({
            "name": "Door 3D", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": attribute.id,
                "value_ids": [(6, 0, attribute.value_ids.ids)],
            })],
        })
        line = template.attribute_line_ids
        # ⓘ Sans caméra, le crochet rend une chaîne vide — jamais `False`, que la
        # colonne afficherait tel quel.
        self.assertEqual(line._configurator_camera_name(), "")

        model3d = self.env["product.model3d"].create(
            {"name": "Panel 3D", "product_tmpl_id": template.id}
        )
        camera = camera_model.create({"name": "Lock close-up", "model3d_id": model3d.id})
        line.view_camera_id = camera
        self.assertEqual(line._configurator_camera_name(), camera.display_name)

    def test_02_and_the_tree_carries_it(self):
        """Le crochet ne sert à rien s'il n'arrive pas jusqu'à l'arbre."""
        attribute = self.env["product.attribute"].create(
            {"name": "Lock 3D bis", "create_variant": "no_variant"}
        )
        self.env["product.attribute.value"].create(
            {"name": "Standard", "attribute_id": attribute.id}
        )
        template = self.env["product.template"].create({
            "name": "Door 3D bis", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": attribute.id,
                "value_ids": [(6, 0, attribute.value_ids.ids)],
            })],
        })
        model3d = self.env["product.model3d"].create(
            {"name": "Panel 3D bis", "product_tmpl_id": template.id}
        )
        camera = self.env["product.model3d.camera"].create(
            {"name": "Front", "model3d_id": model3d.id}
        )
        template.attribute_line_ids.view_camera_id = camera
        arbre = template.get_configurator_tree()
        attributs = [row for row in arbre if row["kind"] == "attribute"]
        self.assertEqual(attributs[0]["camera"], camera.display_name)
