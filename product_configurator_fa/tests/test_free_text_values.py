from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon


class FreeTextValues(BaseCommon):
    """Une saisie TEXTE devient une valeur, comme un nombre — D-353.

    Arbitrages de Gerry (2026-09-25) : *« comme pour le nombre, le texte ajoute une
    valeur à l'attribut »* ; *« avant d'ajouter la valeur, il faut comparer avec les
    valeurs existantes pour les réutiliser »* ; et garder la simple saisie pour des
    prénoms — ce que fait un attribut `no_variant`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        cls.Value = cls.env["product.attribute.value"]
        cls.attr_wood = Attribute.create({
            "name": "Wood", "val_custom": True, "custom_type": "char",
            "create_variant": "dynamic",
        })
        cls.oak = cls.Value.create({"name": "Chêne massif", "attribute_id": cls.attr_wood.id})
        cls.attr_name = Attribute.create({
            "name": "First name", "val_custom": True, "custom_type": "char",
            "create_variant": "no_variant",
        })
        cls.attr_code = Attribute.create({
            "name": "Plate code", "val_custom": True, "custom_type": "char",
            "create_variant": "dynamic",
        })
        cls.attr_width = Attribute.create({
            "name": "Width", "val_custom": True, "custom_type": "float",
            "uom_id": cls.env.ref("uom.product_uom_millimeter").id,
            "create_variant": "dynamic",
        })
        cls.template = cls.env["product.template"].create(
            {"name": "Crate", "config_ok": True}
        )
        Line = cls.env["product.template.attribute.line"]
        cls.line_wood = Line.create({
            "product_tmpl_id": cls.template.id, "attribute_id": cls.attr_wood.id,
            "custom": True, "required": False, "value_ids": [(6, 0, cls.oak.ids)],
            "max_length": 20,
        })
        cls.line_name = Line.create({
            "product_tmpl_id": cls.template.id, "attribute_id": cls.attr_name.id,
            "custom": True, "required": False,
        })
        cls.line_code = Line.create({
            "product_tmpl_id": cls.template.id, "attribute_id": cls.attr_code.id,
            "custom": True, "required": False, "regexp": r"[A-Z]{2}\d{2}",
        })
        cls.line_width = Line.create({
            "product_tmpl_id": cls.template.id, "attribute_id": cls.attr_width.id,
            "custom": True, "required": False,
            "has_min_val": True, "min_val": 100, "has_max_val": True, "max_val": 600,
        })

    def _session(self, **typed):
        session = self.env["product.config.session"].create(
            {"product_tmpl_id": self.template.id, "user_id": self.env.user.id}
        )
        for attribute, text in typed.items():
            self.env["product.config.session.custom.value"].create({
                "attribute_id": getattr(self, attribute).id,
                "cfg_session_id": session.id, "value": text,
            })
        return session

    # ── la valeur naît, et se RÉUTILISE ──────────────────────────────────────

    def test_01_a_typed_text_becomes_a_value_on_the_line(self):
        value = self.line_wood.resolve_custom_value("  Frêne  ")
        self.assertEqual(value.name, "Frêne", "espaces en trop rognés, écriture gardée")
        self.assertTrue(value.configurator_generated)
        self.assertIn(value, self.line_wood.value_ids)

    def test_02_an_existing_value_is_REUSED_whatever_its_case(self):
        before = self.Value.search_count([("attribute_id", "=", self.attr_wood.id)])
        value = self.line_wood.resolve_custom_value("  chêne   MASSIF ")
        self.assertEqual(value, self.oak)
        self.assertEqual(
            self.Value.search_count([("attribute_id", "=", self.attr_wood.id)]), before)

    def test_03_an_archived_text_comes_back_instead_of_doubling(self):
        first = self.line_wood.resolve_custom_value("Hêtre")
        first.active = False
        again = self.line_wood.resolve_custom_value("hêtre")
        self.assertEqual(again, first)
        self.assertTrue(again.active)

    def test_04_a_value_OFFERED_by_the_line_is_a_choice(self):
        self.assertEqual(self.line_wood.offered_value_for("CHÊNE MASSIF"), self.oak)
        self.assertFalse(self.line_wood.offered_value_for("Frêne"))

    def test_05_the_same_number_is_found_whatever_its_writing(self):
        value = self.line_width.resolve_custom_value("480")
        self.assertEqual(self.attr_width.find_custom_value("480,0"), value)
        self.assertEqual(self.attr_width.find_custom_value(" 480 "), value)

    # ── ce qui NE devient PAS une valeur ─────────────────────────────────────

    def test_06_a_no_variant_answer_stays_in_the_session(self):
        """Des prénoms : on ne veut pas un article par prénom."""
        self.assertFalse(self.attr_name._resolves_to_values())
        session = self._session(attr_name="Paul")
        variant = session.create_get_variant()
        self.assertFalse(self.Value.search([("attribute_id", "=", self.attr_name.id)]))
        self.assertEqual(session.custom_value_ids.value, "Paul", "la trace reste")
        self.assertTrue(variant)

    def test_07_a_product_or_material_answer_is_never_typed(self):
        product_attr = self.env["product.attribute"].create(
            {"name": "Handle", "value_type": "product", "create_variant": "dynamic"})
        self.assertFalse(product_attr._resolves_to_values())

    # ── la variante ──────────────────────────────────────────────────────────

    def test_08_same_text_same_variant_other_text_other_variant(self):
        ash = self._session(attr_wood="Frêne").create_get_variant()
        again = self._session(attr_wood="  frêne ").create_get_variant()
        other = self._session(attr_wood="Hêtre").create_get_variant()
        self.assertEqual(ash, again, "la casse ne fait pas un second article")
        self.assertNotEqual(ash, other)

    # ── le contrôle, AU SERVEUR ──────────────────────────────────────────────

    def test_09_a_text_longer_than_allowed_is_refused(self):
        with self.assertRaisesRegex(ValidationError, "at most 20 characters"):
            self.line_wood.validate_custom_val("x" * 21)
        self.line_wood.validate_custom_val("x" * 20)

    def test_10_the_accepted_format_must_match_ENTIRELY(self):
        self.line_code.validate_custom_val("AB12")
        with self.assertRaisesRegex(ValidationError, "format"):
            self.line_code.validate_custom_val("AB123")

    def test_11_a_broken_format_is_the_AUTHORS_fault_not_the_clients(self):
        self.line_code.regexp = "[A-Z"
        self.line_code.validate_custom_val("anything")

    def test_12_a_number_is_read_with_its_COMMA_and_bounded(self):
        """⚠️ `literal_eval("2,5")` levait : un clavier français ne passait pas."""
        self.line_width.validate_custom_val("480,5")
        with self.assertRaisesRegex(ValidationError, "above the maximum"):
            self.line_width.validate_custom_val("900")
        with self.assertRaisesRegex(ValidationError, "not a number"):
            self.line_width.validate_custom_val("wide")
