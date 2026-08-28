from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon


class VisibilityConditions(BaseCommon):
    """Les conditions de visibilité — lot 4 (D-080, D-086, D-087, D-097).

    Le cas de Gerry : le montage arrière fait apparaître un renfort, et la
    largeur — un attribut NUMÉRIQUE, donc sans valeurs à écarter — doit pouvoir
    disparaître elle aussi.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attr_mounting = cls.env["product.attribute"].create(
            {"name": "Mounting", "create_variant": "no_variant"}
        )
        cls.value_front = cls.env["product.attribute.value"].create(
            {"name": "Front", "attribute_id": cls.attr_mounting.id}
        )
        cls.value_rear = cls.env["product.attribute.value"].create(
            {"name": "Rear", "attribute_id": cls.attr_mounting.id}
        )
        cls.attr_brace = cls.env["product.attribute"].create(
            {"name": "Central brace", "create_variant": "no_variant"}
        )
        cls.value_brace_yes = cls.env["product.attribute.value"].create(
            {"name": "With brace", "attribute_id": cls.attr_brace.id}
        )
        cls.attr_width = cls.env["product.attribute"].create(
            {
                "name": "Width",
                "val_custom": True,
                "custom_type": "float",
                "uom_id": cls.env.ref("uom.product_uom_millimeter").id,
                "create_variant": "no_variant",
            }
        )
        cls.template = cls.env["product.template"].create(
            {"name": "Braced Door", "config_ok": True}
        )
        cls.line_mounting = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attr_mounting.id,
                "value_ids": [(6, 0, [cls.value_front.id, cls.value_rear.id])],
                "required": False,
            }
        )
        cls.domain_rear = cls.env["product.config.domain"].create(
            {
                "name": "Rear mounting",
                "domain_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.attr_mounting.id,
                            "condition": "in",
                            "operator": "and",
                            "value_ids": [(6, 0, [cls.value_rear.id])],
                        },
                    )
                ],
            }
        )
        cls.line_brace = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attr_brace.id,
                "value_ids": [(6, 0, [cls.value_brace_yes.id])],
                "required": True,
                "visibility_domain_id": cls.domain_rear.id,
            }
        )
        cls.line_width = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attr_width.id,
                "custom": True,
                "required": False,
                "visibility_domain_id": cls.domain_rear.id,
            }
        )
        cls.session = cls.env["product.config.session"].create(
            {"product_tmpl_id": cls.template.id, "user_id": cls.env.user.id}
        )

    # ── le niveau du MILIEU, celui qui n'existait pas ────────────────────────

    def test_01_an_attribute_hides_by_an_explicit_condition(self):
        self.assertFalse(self.line_brace._is_visible([self.value_front.id]))
        self.assertTrue(self.line_brace._is_visible([self.value_rear.id]))

    def test_02_a_NUMERIC_attribute_can_be_hidden_too(self):
        """⚠️ Le défaut que D-086 nomme : sans valeurs à écarter, l'effet de
        bord n'avait rien à quoi s'accrocher — largeur et hauteur ne pouvaient
        PAS être masquées."""
        self.assertFalse(self.line_width.value_ids, "un numérique n'a pas de valeurs")
        self.assertFalse(self.line_width._is_visible([self.value_front.id]))
        self.assertTrue(self.line_width._is_visible([self.value_rear.id]))

    def test_03_without_a_condition_an_attribute_is_always_asked(self):
        self.assertTrue(self.line_mounting._is_visible([]))
        self.assertTrue(self.line_mounting._is_visible([self.value_front.id]))

    def test_04_a_hidden_attribute_is_not_required(self):
        """⚠️ Sinon la configuration est bloquée par un attribut que personne
        ne voit — et rien n'indique quoi faire pour la débloquer."""
        self.session.validate_configuration(
            value_ids=[self.value_front.id], custom_vals={}, final=True
        )
        with self.assertRaises(ValidationError):
            self.session.validate_configuration(
                value_ids=[self.value_rear.id], custom_vals={}, final=True
            )

    # ── le niveau de l'ÉTAPE ─────────────────────────────────────────────────

    def test_05_a_step_hides_by_its_condition(self):
        step = self.env["product.config.step"].create({"name": "Reinforcement"})
        # ⚠️ L'appartenance ne se coche plus : l'étape est un SÉPARATEUR (D-202),
        # et la ligne qui la porte l'OUVRE — ce qui suit lui appartient. Poser le
        # marqueur déclare l'étape sur le produit, d'où la recherche ensuite.
        self.line_brace.config_step_id = step
        step_line = self.env["product.config.step.line"].search([
            ("product_tmpl_id", "=", self.template.id),
            ("config_step_id", "=", step.id),
        ])
        step_line.visibility_domain_id = self.domain_rear
        self.assertFalse(step_line._is_visible([self.value_front.id]))
        self.assertTrue(step_line._is_visible([self.value_rear.id]))
        self.assertNotIn(
            step_line,
            self.session.get_open_step_lines(value_ids=[self.value_front.id]),
            "une étape masquée ne s'ouvre pas, même si ses attributs ont des "
            "valeurs disponibles",
        )
        self.assertIn(
            step_line,
            self.session.get_open_step_lines(value_ids=[self.value_rear.id]),
        )

    # ── le pont vers l'éditeur de conditions ─────────────────────────────────

    def test_06_a_condition_reads_as_an_editor_domain(self):
        domain = self.domain_rear.to_odoo_domain()
        self.assertEqual(
            domain,
            [(f"__attribute_{self.attr_mounting.id}", "in", [self.value_rear.id])],
        )

    def test_07_an_editor_domain_writes_back(self):
        blank = self.env["product.config.domain"].create(
            {
                "name": "Front mounting",
                "domain_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": self.attr_mounting.id,
                            "condition": "in",
                            "operator": "and",
                            "value_ids": [(6, 0, [self.value_rear.id])],
                        },
                    )
                ],
            }
        )
        blank.from_odoo_domain(
            [(f"__attribute_{self.attr_mounting.id}", "not in", [self.value_rear.id])]
        )
        self.assertEqual(len(blank.domain_line_ids), 1)
        self.assertEqual(blank.domain_line_ids.condition, "not in")
        self.assertEqual(blank.domain_line_ids.value_ids, self.value_rear)

    def test_08_the_editor_cannot_write_what_the_record_would_lose(self):
        """⚠️ Le `DomainSelector` sait exprimer plus que les lignes d'OCA ne
        savent garder. Branché tel quel, il perdrait la condition EN SILENCE."""
        for impossible in (
            [("list_price", ">", 100)],
            [(f"__attribute_{self.attr_mounting.id}", ">", 3)],
            ["!", (f"__attribute_{self.attr_mounting.id}", "in", [1])],
            ["&", (f"__attribute_{self.attr_mounting.id}", "in", [1])],
        ):
            with self.assertRaises(ValidationError):
                self.domain_rear.from_odoo_domain(impossible)

    def test_09_a_round_trip_keeps_the_condition(self):
        domain = self.domain_rear.to_odoo_domain()
        self.domain_rear.from_odoo_domain(domain)
        self.assertEqual(self.domain_rear.to_odoo_domain(), domain)

    # ── la liste de champs du dialogue ───────────────────────────────────────

    def test_10_fields_get_offers_the_attributes_not_image_1024(self):
        fields = self.template.with_context(
            configurator_domain_tmpl_id=self.template.id
        ).fields_get()
        name = f"__attribute_{self.attr_mounting.id}"
        self.assertIn(name, fields)
        self.assertEqual(fields[name]["string"], "Mounting")
        self.assertEqual(fields[name]["relation"], "product.attribute.value")

    def test_11_the_fake_fields_never_leak_outside_the_dialog(self):
        """⚠️ Ces champs n'existent pas : partout ailleurs, ils casseraient les
        vues, les exports et les filtres."""
        fields = self.template.fields_get()
        self.assertNotIn(f"__attribute_{self.attr_mounting.id}", fields)

    def test_12_even_a_numeric_attribute_is_offered_by_its_VALUES(self):
        """Décrire une dimension en `float` laisserait construire
        « largeur > 4000 », que le stockage perdrait (D-080)."""
        fields = self.template.with_context(
            configurator_domain_tmpl_id=self.template.id
        ).fields_get()
        name = f"__attribute_{self.attr_width.id}"
        self.assertEqual(fields[name]["type"], "many2one")
