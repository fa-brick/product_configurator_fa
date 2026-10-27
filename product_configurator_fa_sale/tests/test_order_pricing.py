#  License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Le prix d'une configuration sur un devis — D-537.

Une remise, appliquée une fois au total ; la liste de prix et la date du DEVIS ; une cote
hors de la grille reconnue comme telle.
"""
from datetime import date, datetime

from odoo import Command

from odoo.addons.base.tests.common import BaseCommon


class OrderPricing(BaseCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.pricelist = env["product.pricelist"].create({
            "name": "Revendeur -10%",
            "item_ids": [Command.create({
                "applied_on": "3_global", "compute_price": "percentage", "percent_price": 10,
            })],
        })
        cls.plate = env["product.product"].create(
            {"name": "Plaque carbone", "list_price": 20, "taxes_id": [Command.clear()]})
        cls.attr_plate = env["product.attribute"].create(
            {"name": "Plaque", "value_type": "product"})
        cls.value_plate = env["product.attribute.value"].create({
            "name": "Carbone", "attribute_id": cls.attr_plate.id, "product_id": cls.plate.id,
        })
        mm = env.ref("uom.product_uom_millimeter")
        cls.attr_width, cls.attr_height = env["product.attribute"].create([
            {"name": name, "val_custom": True, "custom_type": "float", "uom_id": mm.id,
             "create_variant": "dynamic"}
            for name in ("Largeur", "Hauteur")
        ])
        cls.template = env["product.template"].create({
            "name": "Portail", "config_ok": True, "list_price": 100,
            "taxes_id": [Command.clear()],
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.attr_plate.id,
                                "value_ids": [Command.set(cls.value_plate.ids)]}),
                Command.create({"attribute_id": cls.attr_width.id, "custom": True,
                                "required": False, "dimension_role": "axis_x"}),
                Command.create({"attribute_id": cls.attr_height.id, "custom": True,
                                "required": False, "dimension_role": "axis_y"}),
            ],
        })
        cls._grid(cls, "Tarif 2026", 500, date(2026, 1, 1), date(2026, 12, 31))
        cls._grid(cls, "Tarif 2027", 525, date(2027, 1, 1), False)
        cls.partner = env["res.partner"].create({"name": "Revendeur"})

    def _grid(self, name, price, start, end):
        grid = self.env["product.price.grid"].create({
            "name": name, "product_tmpl_id": self.template.id,
            "date_start": start, "date_end": end,
        })
        brackets = self.env["product.price.grid.bracket"].create([
            {"grid_id": grid.id, "axis": "x", "max_value": 3000},
            {"grid_id": grid.id, "axis": "y", "max_value": 2400},
        ])
        self.env["product.price.grid.cell"].create({
            "grid_id": grid.id, "x_bracket_id": brackets[0].id,
            "y_bracket_id": brackets[1].id, "price": price,
        })

    def _session(self, width=2000, height=2000):
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.template.id, "user_id": self.env.user.id,
            "value_ids": [Command.set(self.value_plate.ids)],
        })
        for attribute, value in ((self.attr_width, width), (self.attr_height, height)):
            if value is not None:
                self.env["product.config.session.custom.value"].create({
                    "attribute_id": attribute.id, "cfg_session_id": session.id,
                    "value": value,
                })
        return session

    def _order(self, day):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id, "pricelist_id": self.pricelist.id,
            "date_order": datetime.combine(day, datetime.min.time()),
        })

    def test_a_component_is_discounted_once(self):
        """−10 % sur (500 + 20), et non 500 − 10 % plus 20 − 19 %."""
        session = self._session()
        price = session.get_cfg_price(
            custom_vals=session._get_custom_vals_dict(),
            pricelist=self.pricelist, date=date(2026, 6, 1))
        self.assertAlmostEqual(price, 468.0, places=2)

    def test_a_quote_uses_its_own_pricelist(self):
        """⚠️ La liste du DEVIS, pas celle de qui calcule : l'utilisateur du test n'a pas de remise."""
        self.assertAlmostEqual(
            self._session()._get_order_price(self._order(date(2026, 6, 1))), 468.0, places=2)

    def test_a_quote_reads_the_grid_of_its_date(self):
        session = self._session()
        self.assertAlmostEqual(
            session._get_order_price(self._order(date(2026, 6, 1))), 468.0, places=2)
        self.assertAlmostEqual(
            session._get_order_price(self._order(date(2027, 2, 1))), 490.5, places=2)

    def test_the_quote_line_takes_the_order_price(self):
        session = self._session()
        variant = session.create_get_variant(value_ids=self.value_plate.ids)
        order = self._order(date(2027, 2, 1))
        line = self.env["sale.order.line"].create({
            "order_id": order.id, "product_id": variant.id, "config_session_id": session.id,
        })
        self.assertAlmostEqual(line.price_unit, 490.5, places=2)

    def test_a_dimension_beyond_the_grid_is_out_of_grid(self):
        self.assertTrue(self._session(width=3500)._is_out_of_grid())
        self.assertFalse(self._session()._is_out_of_grid())

    def test_a_missing_dimension_is_not_out_of_grid(self):
        """Une cote encore vide : la configuration est incomplète, pas hors grille."""
        self.assertFalse(self._session(height=None)._is_out_of_grid())
