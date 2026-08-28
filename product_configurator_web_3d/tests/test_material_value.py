"""Une valeur peut DÉSIGNER une matière — D-196.

Le type « matière » existait comme un libellé du `Selection`, et rien ne le
suivait : aucune colonne de la valeur ne pointait une fiche matière. Ces tests
éprouvent le chaînon, et le fait que la miniature n'est pas RECOPIÉE.
"""

from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon

#: Deux PNG d'un pixel — assez pour distinguer « avant » de « après ».
RED_PIXEL = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
    b"IQAAAABJRU5ErkJggg=="
)
BLUE_PIXEL = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9"
    b"awAAAABJRU5ErkJggg=="
)


class MaterialValue(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.material = cls.env["product.model3d.material"].create({"name": "Oak"})
        cls.other = cls.env["product.model3d.material"].create({"name": "Brushed steel"})

    def test_01_a_material_type_attribute_points_at_a_material(self):
        attribute = self.env["product.attribute"].create({
            "name": "Finish", "create_variant": "no_variant",
            "value_type": "material",
        })
        value = self.env["product.attribute.value"].create({
            "name": "Oak", "attribute_id": attribute.id,
            "material_id": self.material.id,
        })
        self.assertEqual(value.material_id, self.material)

    def test_02_and_no_OTHER_type_may(self):
        """⚠️ Seconde barrière : la vue masque la colonne, ceci refuse la donnée."""
        for value_type in ("value", "product"):
            attribute = self.env["product.attribute"].create({
                "name": f"Finish {value_type}", "create_variant": "no_variant",
                "value_type": value_type,
            })
            with self.assertRaises(ValidationError):
                self.env["product.attribute.value"].create({
                    "name": "Oak", "attribute_id": attribute.id,
                    "material_id": self.material.id,
                })

    def test_03_the_preview_is_READ_from_the_catalog_never_copied(self):
        """⚠️ Recopier l'image la ferait DIVERGER à la première retouche.

        Éprouvé par le COMPORTEMENT et non par la forme du champ : on régénère la
        miniature de la matière, et la valeur doit montrer la NOUVELLE. Une copie
        faite à la création montrerait encore l'ancienne — et rien, dans la
        déclaration du champ, ne dirait laquelle des deux on lit.
        """
        attribute = self.env["product.attribute"].create({
            "name": "Finish followed", "create_variant": "no_variant",
            "value_type": "material",
        })
        value = self.env["product.attribute.value"].create({
            "name": "Oak", "attribute_id": attribute.id,
            "material_id": self.material.id,
        })
        self.material.sudo().preview_image = RED_PIXEL
        value.invalidate_recordset()
        self.assertEqual(value.material_preview, self.material.preview_image)

        self.material.sudo().preview_image = BLUE_PIXEL
        value.invalidate_recordset()
        self.assertEqual(value.material_preview, self.material.preview_image)

    def test_04_a_material_still_designated_cannot_VANISH(self):
        """`restrict` et non `cascade` : la valeur perdrait ce qu'elle désigne."""
        attribute = self.env["product.attribute"].create({
            "name": "Finish kept", "create_variant": "no_variant",
            "value_type": "material",
        })
        self.env["product.attribute.value"].create({
            "name": "Steel", "attribute_id": attribute.id,
            "material_id": self.other.id,
        })
        with self.assertRaises(Exception):
            self.other.unlink()
