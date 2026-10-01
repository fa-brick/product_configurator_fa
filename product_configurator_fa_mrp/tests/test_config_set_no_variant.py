"""Une condition de nomenclature ne cite pas de réponse « sans variante » — W-99 / D-393."""
from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon


class ConfigSetNoVariant(BaseCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.finish = Value.create({"name": "Brillant", "attribute_id": Attribute.create(
            {"name": "Finition", "create_variant": "no_variant"}).id})
        cls.plate = Value.create({"name": "Cine", "attribute_id": Attribute.create(
            {"name": "Plaque", "create_variant": "dynamic"}).id})
        cls.config_set = cls.env["mrp.bom.line.configuration.set"].create({"name": "Ensemble"})

    def _configuration(self, value):
        return self.env["mrp.bom.line.configuration"].create(
            {"config_set_id": self.config_set.id, "value_ids": [(6, 0, value.ids)]})

    def test_01_une_valeur_qui_cree_des_variantes_est_acceptee(self):
        self.assertTrue(self._configuration(self.plate))

    def test_02_une_reponse_sans_variante_est_refusee(self):
        # ⓘ `assertRaises` d'Odoo (point de sauvegarde), pas `assertRaisesRegex` : le refus
        # laisserait sinon la condition dans le cache du test (L-482).
        with self.assertRaises(ValidationError) as refused:
            self._configuration(self.finish)
        self.assertIn("create no variant", str(refused.exception))
