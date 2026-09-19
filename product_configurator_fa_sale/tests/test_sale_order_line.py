#  Copyright 2024 Simone Rubino - Aion Tech
#  License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.fields import first
from odoo.tests import Form

from odoo.addons.base.tests.common import BaseCommon


class TestSaleOrderLine(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Test partner",
            }
        )
        cls.sale_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
            }
        )

        attribute_form = Form(cls.env["product.attribute"])
        attribute_form.name = "Test attribute"
        with attribute_form.value_ids.new() as value:
            value.name = "Test value 1"
        with attribute_form.value_ids.new() as value:
            value.name = "Test value 2"
        cls.attribute = attribute_form.save()

        product_template_form = Form(cls.env["product.template"])
        product_template_form.name = "Test configurable template"
        product_template_form.taxes_id.clear()
        with product_template_form.attribute_line_ids.new() as attribute_line:
            attribute_line.attribute_id = cls.attribute
            for value in cls.attribute.value_ids:
                attribute_line.value_ids.add(value)
        product_template = product_template_form.save()
        product_template.config_ok = True
        cls.product_template = product_template

    def _configure_product(self, sale_order, product_template, template_values):
        """Poser sur le devis une ligne CONFIGURÉE, avec sa session.

        ⚠️ **Ce passage ne passe plus par l'assistant OCA** : il est mort le
        2026-09-19 (*« pour moi le wizard est mort, on peut le supprimer »*), et
        `action_config_start` avec lui.

        ⓘ Ce que ce banc mesure n'a jamais été l'assistant : c'est que **le prix
        de la ligne suit celui de sa session**. L'assistant n'était que le moyen
        d'obtenir une ligne configurée. On l'obtient désormais comme le fait le
        configurateur 3D — une session, ses valeurs, sa variante — et la règle
        mesurée reste exactement la même.
        """
        session = self.env["product.config.session"].create_get_session(
            product_template.id, force_create=True
        )
        session.value_ids = [(
            6, 0,
            [ptav.product_attribute_value_id.id for ptav in template_values.values()],
        )]
        variant = session.create_get_variant()
        session.action_confirm(product_id=variant)
        return self.env["sale.order.line"].create({
            "order_id": sale_order.id,
            "product_id": variant.id,
            "product_uom_qty": 1,
            "config_session_id": session.id,
        })

    def test_config_session_change_price_unit(self):
        """
        The unit price is the price of the configuration session.
        """
        # Arrange: create a product with 2 product template attribute values
        # having extra price 10 and 20 respectively
        product_template = self.product_template
        ptavs = product_template.attribute_line_ids.product_template_value_ids
        ptav_10 = first(ptavs)
        ptav_10.price_extra = 10
        ptav_20 = first(ptavs - ptav_10)
        ptav_20.price_extra = 20
        attribute = ptav_10.attribute_id
        sale_order = self.sale_order
        self.assertEqual(ptav_10.price_extra, 10)
        self.assertEqual(ptav_20.price_extra, 20)
        self.assertTrue(product_template.config_ok)
        self.assertFalse(sale_order.order_line)

        # Act: Create two order lines, each having a different template attribute value
        self._configure_product(
            sale_order,
            product_template,
            {
                attribute: ptav_10,
            },
        )
        order_line_10 = sale_order.order_line
        self._configure_product(
            sale_order,
            product_template,
            {
                attribute: ptav_20,
            },
        )
        order_line_20 = sale_order.order_line - order_line_10

        # Assert: Each line has the unit price of the configuration session
        config_session_10 = order_line_10.config_session_id
        self.assertEqual(config_session_10.price, order_line_10.price_unit)
        config_session_20 = order_line_20.config_session_id
        self.assertEqual(config_session_20.price, order_line_20.price_unit)
        # Changing the configuration session changes the unit price
        order_line_20.config_session_id = config_session_10
        self.assertEqual(config_session_10.price, order_line_20.price_unit)
