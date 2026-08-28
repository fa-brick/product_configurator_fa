"""L'étape est un SÉPARATEUR — B1, D-202.

⚠️ *« Ce qui suit lui appartient, jusqu'au suivant. »* L'appartenance n'est plus
cochée, elle est **déduite de l'ordre** — et c'est un effet à distance : glisser
une ligne change son étape, sans que rien ne soit saisi.
"""

from odoo.addons.base.tests.common import BaseCommon


class ConfigStepSeparator(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.step_a, cls.step_b = cls.env["product.config.step"].create([
            {"name": "Dimensions"}, {"name": "Finition"},
        ])
        cls.attributes = cls.env["product.attribute"].create([
            {"name": f"Attr {n}", "create_variant": "no_variant"} for n in "ABCD"
        ])
        for attribute in cls.attributes:
            cls.env["product.attribute.value"].create(
                {"name": f"v{attribute.name}", "attribute_id": attribute.id}
            )
        cls.template = cls.env["product.template"].create({
            "name": "Panel B1", "config_ok": True,
            "attribute_line_ids": [
                (0, 0, {
                    "attribute_id": attribute.id,
                    "value_ids": [(6, 0, attribute.value_ids.ids)],
                    "sequence": (index + 1) * 10,
                })
                for index, attribute in enumerate(cls.attributes)
            ],
        })

    def _line(self, letter):
        return self.template.attribute_line_ids.filtered(
            lambda l, n=letter: l.attribute_id.name == f"Attr {n}"
        )

    def _step_line(self, step):
        return self.template.config_step_line_ids.filtered(
            lambda s, st=step: s.config_step_id == st
        )

    # ── ce que le séparateur veut dire ──────────────────────────────────────
    def test_01_what_follows_a_marker_BELONGS_to_it(self):
        self._line("B").config_step_id = self.step_a
        self.assertFalse(self._line("A").config_step_owner_id, "A précède l'étape")
        for letter in ("B", "C", "D"):
            self.assertEqual(self._line(letter).config_step_owner_id, self.step_a)

    def test_02_and_it_stops_at_the_NEXT_marker(self):
        self._line("A").config_step_id = self.step_a
        self._line("C").config_step_id = self.step_b
        self.assertEqual(self._line("B").config_step_owner_id, self.step_a)
        self.assertEqual(self._line("D").config_step_owner_id, self.step_b)

    def test_03_lines_may_live_BEFORE_the_first_step(self):
        """QA, arbitré : rien n'oblige la liste à s'ouvrir par une étape."""
        self._line("C").config_step_id = self.step_a
        self.assertFalse(self._line("A").config_step_owner_id)
        self.assertFalse(self._line("B").config_step_owner_id)

    # ── l'effet à distance, celui qu'il faut montrer ────────────────────────
    def test_04_MOVING_a_line_changes_its_step_silently(self):
        """⚠️ C'est le prix du séparateur, et il doit être éprouvé.

        Aucune saisie, aucun clic sur l'étape : seul l'ordre a bougé, et
        l'appartenance a suivi.
        """
        self._line("C").config_step_id = self.step_a
        self.assertFalse(self._line("B").config_step_owner_id)
        self._line("B").sequence = 35          # B passe APRÈS C
        self.template.invalidate_recordset()
        self.assertEqual(self._line("B").config_step_owner_id, self.step_a)

    # ── ce que l'étape publie, et que tout le reste lit ─────────────────────
    def test_05_the_step_PUBLISHES_the_lines_that_follow_it(self):
        """`attribute_line_ids` garde son nom et son sens — l'assistant le lit."""
        self._line("B").config_step_id = self.step_a
        self._line("D").config_step_id = self.step_b
        self.assertEqual(
            self._step_line(self.step_a).attribute_line_ids,
            self._line("B") + self._line("C"),
        )
        self.assertEqual(
            self._step_line(self.step_b).attribute_line_ids, self._line("D")
        )

    def test_06_marking_a_step_DECLARES_it_on_the_product(self):
        """Sans son enregistrement, l'étape n'aurait ni condition ni existence."""
        self.assertFalse(self.template.config_step_line_ids)
        self._line("B").config_step_id = self.step_a
        self.assertTrue(self._step_line(self.step_a))

    def test_07_the_step_RANK_follows_the_line_that_opens_it(self):
        """⚠️ Deux poignées de tri auraient donné des rangs incomparables."""
        self._line("C").config_step_id = self.step_a
        self.assertEqual(self._step_line(self.step_a).sequence, self._line("C").sequence)

    # ── QA : l'obligation est DÉRIVÉE ───────────────────────────────────────
    def test_08_a_step_is_required_when_it_carries_a_required_attribute(self):
        self._line("B").config_step_id = self.step_a
        self._line("B").required = False
        self._line("C").required = False
        self._line("D").required = False
        self.assertFalse(self._step_line(self.step_a).required)
        self._line("C").required = True
        self.template.invalidate_recordset()
        self.assertTrue(self._step_line(self.step_a).required)

    def test_09_a_step_cannot_be_declared_TWICE_on_a_product(self):
        """Deux lignes pour la même étape se disputeraient les mêmes attributs.

        ⓘ L'invariant est tenu par `_check_config_step`, qui existait AVANT ce
        chantier. Ce test le rattache au séparateur — la règle vaut désormais
        pour une autre raison qu'à l'origine, et elle doit tenir.
        """
        from odoo.exceptions import ValidationError
        self._line("B").config_step_id = self.step_a
        with self.assertRaises(ValidationError):
            self.env["product.config.step.line"].create({
                "product_tmpl_id": self.template.id,
                "config_step_id": self.step_a.id,
            })
