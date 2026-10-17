from odoo.addons.base.tests.common import BaseCommon


class ProductConfiguratorTestCases(BaseCommon):
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

    @classmethod
    def _configure_product(cls):
        """Configurer la BMW de démonstration par sa SESSION, le chemin de la page 3D.

        ⓘ Les réponses sont celles où arrivait l'ancien parcours de l'assistant OCA, retiré
        (D-497).
        ⚠️ Sans `force_create` : la session brouillon déjà ouverte par le test est celle
        qu'on configure, comme le faisait l'assistant.
        """
        session = cls.env["product.config.session"].create_get_session(
            cls.config_product.id
        )
        session.value_ids = (
            cls.value_gasoline + cls.value_220i + cls.value_red + cls.value_rims_378
            + cls.value_model_sport_line + cls.value_tapistry + cls.value_transmission
            + cls.value_options_2
        )
        session.action_confirm()
        return session
