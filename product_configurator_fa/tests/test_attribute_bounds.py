from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon


class AttributeBounds(BaseCommon):
    """Les bornes d'un attribut numérique — lot 1 (D-076, D-077, D-089).

    Le scénario est celui de Gerry : une largeur bornée à 5 000, que le montage
    arrière ramène à 4 000.
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
        cls.attr_width = cls.env["product.attribute"].create(
            {
                "name": "Width",
                "val_custom": True,
                "custom_type": "float",
                "create_variant": "no_variant",
            }
        )
        cls.template = cls.env["product.template"].create({"name": "Bounded Door"})
        cls.line_mounting = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attr_mounting.id,
                "value_ids": [(6, 0, [cls.value_front.id, cls.value_rear.id])],
            }
        )
        cls.line_width = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attr_width.id,
                "custom": True,
                "has_max_val": True,
                "max_val": 5000,
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

    # ── les bornes par défaut ────────────────────────────────────────────────

    def test_01_default_bounds_apply(self):
        """Sans condition satisfaite, ce sont les bornes de la ligne qui valent."""
        bounds = self.line_width._get_bounds()
        self.assertEqual(bounds["max_val"], 5000)
        self.assertIsNone(bounds["min_val"])
        self.assertIsNone(bounds["cause"])
        self.line_width.validate_custom_val(5000)
        with self.assertRaises(ValidationError):
            self.line_width.validate_custom_val(5001)

    def test_02_bounds_live_on_the_line_not_the_attribute(self):
        """D-089 — deux produits, deux bornes pour le MÊME attribut global."""
        other_template = self.env["product.template"].create({"name": "Small Door"})
        other_line = self.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": other_template.id,
                "attribute_id": self.attr_width.id,
                "custom": True,
                "has_max_val": True,
                "max_val": 3000,
            }
        )
        self.line_width.validate_custom_val(4000)
        with self.assertRaises(ValidationError):
            other_line.validate_custom_val(4000)
        self.assertNotIn("min_val", self.env["product.attribute"]._fields)

    # ── la borne conditionnelle ──────────────────────────────────────────────

    def test_03_conditional_bound_wins(self):
        """« Le montage arrière limite la largeur à 4 000 » — D-076."""
        self.env["product.attribute.bound"].create(
            {
                "attribute_line_id": self.line_width.id,
                "domain_id": self.domain_rear.id,
                "has_max_val": True,
                "max_val": 4000,
            }
        )
        # montage AVANT : la borne par défaut tient
        bounds = self.line_width._get_bounds(value_ids=[self.value_front.id])
        self.assertEqual(bounds["max_val"], 5000)
        self.line_width.validate_custom_val(4500, value_ids=[self.value_front.id])

        # montage ARRIÈRE : la borne conditionnelle prend la main
        bounds = self.line_width._get_bounds(value_ids=[self.value_rear.id])
        self.assertEqual(bounds["max_val"], 4000)
        self.assertEqual(bounds["cause"], "Rear mounting")
        with self.assertRaises(ValidationError) as caught:
            self.line_width.validate_custom_val(4500, value_ids=[self.value_rear.id])
        message = str(caught.exception)
        self.assertIn("4000", message, "la borne doit être nommée")
        self.assertIn("Rear mounting", message, "la CAUSE doit être nommée (D-077)")

    def test_04_first_matching_bound_wins(self):
        """L'ordre décide — et il est celui de `sequence`, pas celui de création."""
        common = {
            "attribute_line_id": self.line_width.id,
            "domain_id": self.domain_rear.id,
            "has_max_val": True,
        }
        self.env["product.attribute.bound"].create(
            dict(common, max_val=4000, sequence=20)
        )
        self.env["product.attribute.bound"].create(
            dict(common, max_val=4200, sequence=10)
        )
        bounds = self.line_width._get_bounds(value_ids=[self.value_rear.id])
        self.assertEqual(bounds["max_val"], 4200)

    def test_05_conditional_bound_replaces_wholly(self):
        """Une borne conditionnelle REMPLACE, elle ne complète pas."""
        self.line_width.write({"has_min_val": True, "min_val": 1000})
        self.env["product.attribute.bound"].create(
            {
                "attribute_line_id": self.line_width.id,
                "domain_id": self.domain_rear.id,
                "has_max_val": True,
                "max_val": 4000,
            }
        )
        bounds = self.line_width._get_bounds(value_ids=[self.value_rear.id])
        self.assertIsNone(
            bounds["min_val"],
            "le mini par défaut ne doit PAS se glisser dans une borne conditionnelle",
        )

    # ── les deux défauts de type qu'OCA portait ──────────────────────────────

    def test_06_zero_is_a_bound_of_its_own(self):
        """`0` n'est plus « pas de borne » — le défaut nommé par D-089."""
        self.line_width.write(
            {"has_min_val": True, "min_val": 0, "has_max_val": False, "max_val": 0}
        )
        self.line_width.validate_custom_val(0)
        with self.assertRaises(ValidationError):
            self.line_width.validate_custom_val(-1)
        # sans le drapeau, la même valeur zéro ne borne plus rien
        self.line_width.write({"has_min_val": False})
        self.line_width.validate_custom_val(-1)

    def test_07_bounds_are_floats(self):
        """Une largeur maxi de 2 400,5 mm était impossible en `Integer`."""
        self.line_width.write({"has_max_val": True, "max_val": 2400.5})
        self.line_width.validate_custom_val(2400.5)
        with self.assertRaises(ValidationError):
            self.line_width.validate_custom_val(2400.6)

    # ── le pas ───────────────────────────────────────────────────────────────

    def test_08_step_is_enforced_and_proposes(self):
        """`1237` avec un pas de 50 passait sans un mot."""
        self.line_width.write(
            {"has_min_val": True, "min_val": 1000, "has_max_val": True,
             "max_val": 5000, "step": 50}
        )
        self.line_width.validate_custom_val(1250)
        with self.assertRaises(ValidationError) as caught:
            self.line_width.validate_custom_val(1237)
        message = str(caught.exception)
        self.assertIn("50", message)
        self.assertIn("1250", message, "la valeur la plus proche doit être PROPOSÉE")

    def test_09_suggestion_stays_inside_the_bounds(self):
        """Le pas ne doit jamais proposer une valeur hors bornes."""
        self.line_width.write(
            {"has_min_val": True, "min_val": 1000, "has_max_val": True,
             "max_val": 1080, "step": 50}
        )
        bounds = self.line_width._get_bounds()
        self.assertEqual(self.line_width._suggest_val(1090, bounds), 1050)
        self.assertEqual(self.line_width._suggest_val(900, bounds), 1000)

    def test_10_step_that_does_not_divide_the_range(self):
        """Le pas part du MINI : c'est lui, et lui seul, qui reste admissible.

        ⚠️ Relevé en écrivant ce test : puisque la base du pas est le mini (ou
        zéro à défaut), une valeur admissible existe presque toujours. Le
        `None` que `_suggest_val` sait rendre est donc une ceinture, pas un cas
        courant — mieux vaut le dire que laisser croire à un cas fréquent.
        """
        self.line_width.write(
            {"has_min_val": True, "min_val": 1010, "has_max_val": True,
             "max_val": 1040, "step": 50}
        )
        bounds = self.line_width._get_bounds()
        self.assertEqual(self.line_width._suggest_val(1020, bounds), 1010)
        self.line_width.validate_custom_val(1010)
        with self.assertRaises(ValidationError):
            self.line_width.validate_custom_val(1040)

    # ── garde-fous ───────────────────────────────────────────────────────────

    def test_11_bounds_cleared_when_attribute_is_not_numeric(self):
        """Une borne sur un attribut texte est une règle inerte affichée."""
        self.env["product.attribute.bound"].create(
            {
                "attribute_line_id": self.line_width.id,
                "domain_id": self.domain_rear.id,
                "has_max_val": True,
                "max_val": 4000,
            }
        )
        # ⚠️ Odoo REFUSE de changer l'attribut d'une ligne enregistrée
        # (`product_template_attribute_line.py:138`) : cet onchange ne joue que
        # sur une ligne en cours de saisie, et c'est là qu'il faut l'éprouver.
        draft = self.env["product.template.attribute.line"].new(
            {
                "product_tmpl_id": self.template.id,
                "attribute_id": self.attr_width.id,
                "custom": True,
                "has_max_val": True,
                "max_val": 5000,
                "step": 50,
            }
        )
        draft.attribute_id = self.attr_mounting
        draft.onchange_attribute()
        self.assertFalse(draft.has_max_val)
        self.assertFalse(draft.step)

    def test_12_inconsistent_bounds_are_refused_everywhere(self):
        """La contrainte vaut pour la ligne ET pour la borne conditionnelle."""
        with self.assertRaises(ValidationError):
            self.env["product.attribute.bound"].create(
                {
                    "attribute_line_id": self.line_width.id,
                    "domain_id": self.domain_rear.id,
                    "has_min_val": True,
                    "min_val": 4000,
                    "has_max_val": True,
                    "max_val": 1000,
                }
            )
        with self.assertRaises(ValidationError):
            self.line_width.write({"step": -50})

    def test_13_non_numeric_attribute_is_never_bounded(self):
        """Un attribut discret n'a pas de borne — la validation passe son tour."""
        self.line_mounting.write({"has_max_val": True, "max_val": 1})
        self.line_mounting.validate_custom_val(999)

    # ── le point de raccordement réel ────────────────────────────────────────

    def test_14_session_validation_goes_through_the_line(self):
        """`check_attributes_configuration` doit passer la configuration COURANTE.

        Sans elle, une borne conditionnelle n'aurait aucun moyen de se choisir —
        c'est tout l'objet du déplacement de l'appel (D-089).
        """
        self.env["product.attribute.bound"].create(
            {
                "attribute_line_id": self.line_width.id,
                "domain_id": self.domain_rear.id,
                "has_max_val": True,
                "max_val": 4000,
            }
        )
        session = self.env["product.config.session"]
        lines = self.line_mounting + self.line_width
        custom_vals = {self.attr_width.id: 4500}
        # montage avant : 4 500 passe
        session.check_attributes_configuration(
            lines, custom_vals, [self.value_front.id], final=False
        )
        # montage arrière : la même valeur est refusée
        with self.assertRaises(ValidationError):
            session.check_attributes_configuration(
                lines, custom_vals, [self.value_rear.id], final=False
            )
