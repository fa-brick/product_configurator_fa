from odoo.addons.base.tests.common import BaseCommon


class ConfigurationCreate(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config_product = cls.env.ref("product_configurator_fa.bmw_2_series")
        cls.product_category = cls.env.ref("product.product_category_5")

        # attributes
        cls.attr_fuel = cls.env.ref("product_configurator_fa.product_attribute_fuel")
        cls.attr_engine = cls.env.ref("product_configurator_fa.product_attribute_engine")
        cls.attr_color = cls.env.ref("product_configurator_fa.product_attribute_color")
        cls.attr_rims = cls.env.ref("product_configurator_fa.product_attribute_rims")
        cls.attr_model_line = cls.env.ref(
            "product_configurator_fa.product_attribute_model_line"
        )
        cls.attr_tapistry = cls.env.ref(
            "product_configurator_fa.product_attribute_tapistry"
        )
        cls.attr_transmission = cls.env.ref(
            "product_configurator_fa.product_attribute_transmission"
        )
        cls.attr_options = cls.env.ref("product_configurator_fa.product_attribute_options")

        # values
        cls.value_gasoline = cls.env.ref(
            "product_configurator_fa.product_attribute_value_gasoline"
        )
        cls.value_218i = cls.env.ref(
            "product_configurator_fa.product_attribute_value_218i"
        )
        cls.value_220i = cls.env.ref(
            "product_configurator_fa.product_attribute_value_220i"
        )
        cls.value_red = cls.env.ref("product_configurator_fa.product_attribute_value_red")
        cls.value_rims_378 = cls.env.ref(
            "product_configurator_fa.product_attribute_value_rims_378"
        )
        cls.value_sport_line = cls.env.ref(
            "product_configurator_fa.product_attribute_value_sport_line"
        )
        cls.value_model_sport_line = cls.env.ref(
            "product_configurator_fa.product_attribute_value_model_sport_line"
        )
        cls.value_tapistry = cls.env.ref(
            "product_configurator_fa.product_attribute_value_tapistry" + "_oyster_black"
        )
        cls.value_transmission = cls.env.ref(
            "product_configurator_fa.product_attribute_value_steptronic"
        )
        cls.value_options_1 = cls.env.ref(
            "product_configurator_fa.product_attribute_value_smoker_package"
        )
        cls.value_options_2 = cls.env.ref(
            "product_configurator_fa.product_attribute_value_sunroof"
        )

    def test_01_create(self):
        """Test configuration item does not make variations"""

        attr_test = self.env["product.attribute"].create(
            {
                "name": "Test",
                "value_ids": [
                    (0, 0, {"name": "1"}),
                    (0, 0, {"name": "2"}),
                ],
            }
        )

        test_template = self.env["product.template"].create(
            {
                "name": "Test Configuration",
                "config_ok": True,
                "type": "consu",
                "categ_id": self.product_category.id,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": attr_test.id,
                            "value_ids": [
                                (6, 0, attr_test.value_ids.ids),
                            ],
                            "required": True,
                        },
                    ),
                ],
            }
        )

        self.assertEqual(
            len(test_template.product_variant_ids),
            0,
            "Create should not have any variants",
        )

        # FIXME: broken as
        # """
        # AttributeError: 'product.product' object
        # has no attribute 'attribute_value_ids'.
        # Did you mean: 'attribute_line_ids'?
        # """
        # new_variant = self.config_product.product_variant_ids.filtered(
        #     lambda variant: variant.attribute_value_ids == value_ids
        # )
        # self.assertNotEqual(
        #     new_variant.id,
        #     False,
        #     "Variant not generated at the end of the configuration process",
        # )
