from psycopg2 import IntegrityError

from odoo.tools import mute_logger

from odoo.addons.base.tests.common import BaseCommon


class DimensionValues(BaseCommon):
    """Une dimension se SAISIT librement mais se RANGE en valeur — lot 2, D-081.

    Le fil rouge est la question de terrain qui a fait changer la voie : deux
    portes de 2 400 et 3 000 doivent être deux articles distincts en stock.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.value_obj = cls.env["product.attribute.value"]
        cls.attr_width = cls.env["product.attribute"].create(
            {
                "name": "Width",
                "val_custom": True,
                "custom_type": "float",
                "uom_id": cls.env.ref("uom.product_uom_millimeter").id,
                # ⚠️ D-081 condition 1 : en `always`, ajouter une largeur créerait
                # aussitôt une variante par combinaison, et Odoo s'arrête à 1 000.
                "create_variant": "dynamic",
            }
        )
        cls.template = cls.env["product.template"].create(
            {"name": "Sliding Door", "config_ok": True}
        )
        cls.line_width = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attr_width.id,
                "custom": True,
                "required": False,
            }
        )

    def _session(self, width):
        session = self.env["product.config.session"].create(
            {"product_tmpl_id": self.template.id, "user_id": self.env.user.id}
        )
        self.env["product.config.session.custom.value"].create(
            {
                "attribute_id": self.attr_width.id,
                "cfg_session_id": session.id,
                "value": width,
            }
        )
        return session

    # ── la résolution ────────────────────────────────────────────────────────

    def test_01_free_entry_becomes_an_attribute_value(self):
        value = self.line_width.resolve_numeric_value("3200")
        self.assertEqual(value.name, "3200")
        self.assertTrue(value.configurator_generated)
        self.assertIn(value, self.line_width.value_ids, "elle doit être SUR la ligne")
        self.assertTrue(
            self.line_width.product_template_value_ids.filtered(
                lambda ptav: ptav.product_attribute_value_id == value
            ),
            "sans ptav, aucune variante ne pourrait la porter",
        )

    def test_02_the_same_number_is_the_same_value(self):
        first = self.line_width.resolve_numeric_value("3200")
        second = self.line_width.resolve_numeric_value(3200)
        third = self.line_width.resolve_numeric_value("3200.0")
        self.assertEqual(first, second)
        self.assertEqual(first, third, "la forme canonique fait l'identité (D-160)")
        self.assertEqual(
            self.value_obj.search_count(
                [("attribute_id", "=", self.attr_width.id), ("name", "=", "3200")]
            ),
            1,
        )

    def test_03_unicity_is_enforced_by_the_DATABASE(self):
        """⚠️ Le vrai garde-fou. Aucun verrou applicatif ne le remplace."""
        self.line_width.resolve_numeric_value("3200")
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.value_obj.create(
                    {"attribute_id": self.attr_width.id, "name": "3200"}
                )
                self.env.flush_all()

    def test_04_an_archived_width_comes_back_instead_of_doubling(self):
        value = self.line_width.resolve_numeric_value("3200")
        value.active = False
        again = self.line_width.resolve_numeric_value("3200")
        self.assertEqual(again, value)
        self.assertTrue(again.active, "une largeur qui revient est la MÊME largeur")

    def test_05_widths_are_ordered_by_their_number(self):
        """Sans séquence, la liste s'afficherait dans l'ordre des VENTES."""
        for width in ("3200", "900", "1500"):
            self.line_width.resolve_numeric_value(width)
        names = self.line_width.value_ids.sorted(
            lambda value: (value.sequence, value.id)
        ).mapped("name")
        self.assertEqual(names, ["900", "1500", "3200"])

    # ── ce que ça change pour le STOCK ───────────────────────────────────────

    def test_06_two_widths_are_two_variants_and_one_width_is_one(self):
        big = self._session(3200).create_get_variant()
        widths = big.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id.name"
        )
        self.assertIn("3200", widths, "la largeur entre dans l'IDENTITÉ de la variante")

        same = self._session(3200).create_get_variant()
        self.assertEqual(big, same, "la même largeur ne fait pas deux articles")

        small = self._session(2400).create_get_variant()
        self.assertNotEqual(
            big, small, "deux largeurs font deux articles — le stock les distingue"
        )

    def test_07_a_no_variant_attribute_is_left_alone(self):
        """Une valeur qui ne peut pas entrer dans une variante n'a rien à ranger."""
        note = self.env["product.attribute"].create(
            {
                "name": "Comment",
                "val_custom": True,
                "custom_type": "integer",
                "create_variant": "no_variant",
            }
        )
        self.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": self.template.id,
                "attribute_id": note.id,
                "custom": True,
                "required": False,
            }
        )
        session = self.env["product.config.session"].create(
            {"product_tmpl_id": self.template.id, "user_id": self.env.user.id}
        )
        self.env["product.config.session.custom.value"].create(
            {"attribute_id": note.id, "cfg_session_id": session.id, "value": "12"}
        )
        session.create_get_variant()
        self.assertFalse(
            self.value_obj.search([("attribute_id", "=", note.id)]),
            "rien ne doit être créé pour un attribut hors variante",
        )

    # ── le ménage ────────────────────────────────────────────────────────────

    def test_08_the_vacuum_archives_what_was_never_sold(self):
        unsold = self.line_width.resolve_numeric_value("4444")
        sold = self._session(3200).create_get_variant()
        sold_value = sold.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id"
        )
        self.env.cr.execute(
            "UPDATE product_attribute_value SET create_date = now() - interval "
            "'200 days' WHERE id IN %s",
            (tuple((unsold + sold_value).ids),),
        )
        self.env.invalidate_all()

        self.value_obj._gc_configurator_values()

        self.assertFalse(unsold.active, "jamais servie et vieille : archivée")
        self.assertNotIn(unsold, self.line_width.value_ids, "et retirée de la ligne")
        self.assertTrue(
            all(sold_value.mapped("active")),
            "une largeur portée par une variante ne bouge JAMAIS",
        )

    def test_09_the_vacuum_spares_recent_and_hand_made_values(self):
        recent = self.line_width.resolve_numeric_value("4444")
        hand_made = self.value_obj.create(
            {"attribute_id": self.attr_width.id, "name": "1234"}
        )
        self.env.cr.execute(
            "UPDATE product_attribute_value SET create_date = now() - interval "
            "'200 days' WHERE id = %s",
            (hand_made.id,),
        )
        self.env.invalidate_all()

        self.value_obj._gc_configurator_values()

        self.assertTrue(recent.active, "trop récente pour être balayée")
        self.assertTrue(
            hand_made.active, "elle n'est pas du configurateur : on n'y touche pas"
        )
