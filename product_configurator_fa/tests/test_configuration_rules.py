#  Copyright 2024 Simone Rubino - Aion Tech
#  License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, Command
from odoo.exceptions import ValidationError
from odoo.fields import first
from odoo.tests import Form, TransactionCase
from odoo.tools.safe_eval import safe_eval


class ConfigurationRules(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The product attribute view only shows configuration fields
        # (such as `val_custom`)
        # when called with a specific context
        # that is set by this action
        configuration_attributes_action = cls.env.ref(
            "product_configurator_fa.action_attributes_view"
        )
        action_eval_context = configuration_attributes_action._get_eval_context()
        configuration_attribute_context = safe_eval(
            configuration_attributes_action.context, globals_dict=action_eval_context
        )
        configuration_attribute_model = cls.env["product.attribute"].with_context(
            **configuration_attribute_context
        )

        cls.generic_custom_attribute_value = cls.env.ref(
            "product_configurator_fa.custom_attribute_value"
        )

        custom_attribute_form = Form(configuration_attribute_model)
        custom_attribute_form.name = "Test custom attribute"
        with custom_attribute_form.value_ids.new() as value:
            value.name = "Test custom value"
        custom_attribute_form.val_custom = True
        cls.custom_attribute = custom_attribute_form.save()
        cls.custom_attribute_value = cls.custom_attribute.value_ids

        other_custom_attribute_form = Form(configuration_attribute_model)
        other_custom_attribute_form.name = "Test other custom attribute"
        other_custom_attribute_form.val_custom = True
        with other_custom_attribute_form.value_ids.new() as value:
            value.name = "Test other custom value"
        cls.other_custom_attribute = other_custom_attribute_form.save()
        cls.other_custom_attribute_value = cls.other_custom_attribute.value_ids

        regular_attribute_form = Form(configuration_attribute_model)
        regular_attribute_form.name = "Test regular attribute"
        regular_attribute_form.val_custom = False
        with regular_attribute_form.value_ids.new() as value:
            value.name = "Test value 1"
        with regular_attribute_form.value_ids.new() as value:
            value.name = "Test value 2"
        cls.regular_attribute = regular_attribute_form.save()
        cls.regular_attribute_value_1 = first(cls.regular_attribute.value_ids)
        cls.regular_attribute_value_2 = (
            cls.regular_attribute.value_ids - cls.regular_attribute_value_1
        )

        config_domain_form = Form(cls.env["product.config.domain"])
        config_domain_form.name = "Regular attribute has value 1"
        with config_domain_form.domain_line_ids.new() as line:
            line.attribute_id = cls.regular_attribute
            line.condition = "in"
            line.value_ids.add(cls.regular_attribute_value_1)
        regular_has_value_1_domain = config_domain_form.save()

        product_template_form = Form(cls.env["product.template"])
        product_template_form.name = "Test configurable product"
        with product_template_form.attribute_line_ids.new() as regular_line:
            regular_line.attribute_id = cls.regular_attribute
            for attribute_value in cls.regular_attribute.value_ids:
                regular_line.value_ids.add(attribute_value)
        with product_template_form.attribute_line_ids.new() as custom_line:
            custom_line.attribute_id = cls.custom_attribute
            for attribute_value in cls.custom_attribute.value_ids:
                custom_line.value_ids.add(attribute_value)
        with product_template_form.attribute_line_ids.new() as other_custom_line:
            other_custom_line.attribute_id = cls.other_custom_attribute
            for attribute_value in cls.other_custom_attribute.value_ids:
                other_custom_line.value_ids.add(attribute_value)
        product_template = product_template_form.save()
        product_template.config_ok = True
        # When the regular attribute has value 1,
        # the custom attribute must have the generic custom value.
        # The other custom attribute id not restricted.
        # ⚠️ `config_line_ids` a QUITTÉ la fiche produit : la section
        # « Configuration Restrictions » a été retirée de l'onglet configurateur
        # (D-213), les conditions par valeur se posant désormais depuis l'arbre.
        # Un `Form` ne peut donc plus l'atteindre — on crée l'enregistrement,
        # c'est ce que l'arbre fait lui aussi.
        cls.env["product.config.line"].create({
            "product_tmpl_id": product_template.id,
            "attribute_line_id": product_template.attribute_line_ids.filtered(
                lambda al: al.attribute_id == cls.custom_attribute
            ).id,
            "value_ids": [(6, 0, [cls.generic_custom_attribute_value.id])],
            "domain_id": regular_has_value_1_domain.id,
        })

        cls.product_template = product_template

    def setUp(self):
        super().setUp()

        self.cfg_tmpl = self.env.ref("product_configurator_fa.bmw_2_series")
        self.cfg_session = self.env["product.config.session"].create(
            {"product_tmpl_id": self.cfg_tmpl.id, "user_id": SUPERUSER_ID}
        )

        attribute_vals = self.cfg_tmpl.attribute_line_ids.mapped("value_ids")
        self.attr_vals = self.cfg_tmpl.attribute_line_ids.mapped("value_ids")

        self.attr_val_ext_ids = {
            v: k for k, v in attribute_vals.get_external_id().items()
        }

    def get_attr_val_ids(self, ext_ids):
        """Return a list of database ids using the external_ids
        passed via ext_ids argument"""

        value_ids = []

        attr_val_prefix = "product_configurator_fa.product_attribute_value_%s"

        for ext_id in ext_ids:
            if ext_id in self.attr_val_ext_ids:
                value_ids.append(self.attr_val_ext_ids[ext_id])
            elif attr_val_prefix % ext_id in self.attr_val_ext_ids:
                value_ids.append(self.attr_val_ext_ids[attr_val_prefix % ext_id])

        return value_ids

    def test_valid_configuration(self):
        """Test validation of a valid configuration"""

        conf = [
            "gasoline",
            "228i",
            "model_luxury_line",
            "silver",
            "rims_384",
            "tapistry_black",
            "steptronic",
            "smoker_package",
            "tow_hook",
        ]

        attr_val_ids = self.get_attr_val_ids(conf)
        validation = self.cfg_session.validate_configuration(attr_val_ids)
        self.assertTrue(validation, "Valid configuration failed validation")

    def test_invalid_configuration(self):
        conf = [
            "diesel",
            "228i",
            "model_luxury_line",
            "silver",
            "rims_384",
            "tapistry_black",
            "steptronic",
            "smoker_package",
            "tow_hook",
        ]

        attr_val_ids = self.get_attr_val_ids(conf)
        with self.assertRaises(ValidationError):
            self.cfg_session.validate_configuration(attr_val_ids)

    def test_missing_val_configuration(self):
        conf = [
            "diesel",
            "228i",
            "model_luxury_line",
            "rims_384",
            "tapistry_black",
            "steptronic",
            "smoker_package",
            "tow_hook",
        ]

        attr_val_ids = self.get_attr_val_ids(conf)
        with self.assertRaises(ValidationError):
            self.cfg_session.validate_configuration(attr_val_ids)

    def test_invalid_multi_configuration(self):
        conf = [
            "gasoline",
            "228i",
            "model_luxury_line",
            "silver",
            "red",
            "rims_384",
            "tapistry_black",
            "steptronic",
            "smoker_package",
            "tow_hook",
        ]

        attr_val_ids = self.get_attr_val_ids(conf)
        with self.assertRaises(ValidationError):
            self.cfg_session.validate_configuration(attr_val_ids)

    def test_invalid_custom_value_configuration(self):
        conf = [
            "gasoline",
            "228i",
            "model_luxury_line",
            "rims_384",
            "tapistry_black",
            "steptronic",
            "smoker_package",
            "tow_hook",
        ]

        attr_color_id = self.env.ref("product_configurator_fa.product_attribute_color")

        custom_vals = {attr_color_id: {"value": "#fefefe"}}

        attr_val_ids = self.get_attr_val_ids(conf)
        with self.assertRaises(ValidationError):
            self.cfg_session.validate_configuration(attr_val_ids, custom_vals)

    def test_filled_custom_value(self):
        """When custom values are restricted,
        filling them correctly creates a valid configuration."""
        # Arrange
        session = self.env["product.config.session"].create_get_session(
            self.product_template.id, force_create=True
        )
        # Regular attribute has value 1
        # so the custom attribute must have the generic custom value.
        # The other custom attribute can have any value.
        session.write({
            "value_ids": [Command.set((
                self.regular_attribute_value_1
                + self.generic_custom_attribute_value
                + self.other_custom_attribute_value
            ).ids)],
            "custom_value_ids": [Command.create({
                "attribute_id": self.custom_attribute.id,
                "value": "5",
            })],
        })

        # Act
        session.action_confirm()

        # Assert
        self.assertEqual(session.state, "done")

    def test_fill_restricted_custom_value(self):
        """When custom values are restricted,
        filling them with the wrong value creates an invalid configuration."""
        # Arrange
        session = self.env["product.config.session"].create_get_session(
            self.product_template.id, force_create=True
        )
        lines = self.product_template.attribute_line_ids

        def available_on(attribute):
            line = lines.filtered(lambda ligne: ligne.attribute_id == attribute)
            return session.values_available(
                check_val_ids=self.generic_custom_attribute_value.ids,
                value_ids=self.regular_attribute_value_2.ids,
                custom_vals={},
                product_template_attribute_line_id=line.id,
            )

        # Assert : regular attribute has value 2, so the custom attribute cannot
        # have the generic custom value ; the other custom attribute can.
        self.assertNotIn(
            self.generic_custom_attribute_value.id, available_on(self.custom_attribute)
        )
        self.assertIn(
            self.generic_custom_attribute_value.id,
            available_on(self.other_custom_attribute),
        )
