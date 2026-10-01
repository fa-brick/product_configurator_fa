# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""LES ÉTAPES sur la page du configurateur — D-385 (Gerry, 2026-09-30).

« Les étapes conditionnent ce qui est vu dans la sidebar » : le serveur range chaque
question dans son étape, ne sert que les étapes VISIBLES, et dit ce qui MANQUE — avec le
même évaluateur que la confirmation, pour que la page ne grise jamais ce qu'il accepterait.
"""
from odoo import Command
from odoo.addons.base.tests.common import BaseCommon


class StepsOnThePage(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.color, cls.plate, cls.print_, cls.finish = Attribute.create([
            {"name": name, "create_variant": "no_variant"}
            for name in ("Color", "Plate", "Print", "Finish")
        ])
        cls.white, cls.black = Value.create([
            {"name": "White", "attribute_id": cls.color.id},
            {"name": "Black", "attribute_id": cls.color.id},
        ])
        cls.carbon = Value.create({"name": "Carbon", "attribute_id": cls.plate.id})
        cls.pla = Value.create({"name": "PLA", "attribute_id": cls.print_.id})
        cls.matte = Value.create({"name": "Matte", "attribute_id": cls.finish.id})
        cls.tmpl = cls.env["product.template"].create({
            "name": "Drone with steps",
            "config_ok": True,
            "attribute_line_ids": [
                Command.create({"attribute_id": attribute.id, "sequence": rank,
                                "value_ids": [Command.set(values.ids)], "required": True})
                for rank, (attribute, values) in enumerate([
                    (cls.color, cls.white | cls.black),
                    (cls.plate, cls.carbon),
                    (cls.print_, cls.pla),
                    (cls.finish, cls.matte),
                ], start=1)
            ],
        })
        cls.lines = {
            line.attribute_id: line for line in cls.tmpl.attribute_line_ids
        }
        cls.frame = cls.env["product.config.step"].create({"name": "Frame"})
        cls.prints = cls.env["product.config.step"].create({"name": "Prints"})
        # Color est AVANT la première étape ; Plate ouvre « Frame », Print ouvre « Prints ».
        cls.lines[cls.plate].config_step_id = cls.frame
        cls.lines[cls.print_].config_step_id = cls.prints

    def _session(self, values=None):
        session = self.env["product.config.session"].create_get_session(
            self.tmpl.id, force_create=True
        )
        session.value_ids = [(6, 0, (values or self.env["product.attribute.value"]).ids)]
        return session

    def _step_line(self, step):
        return self.tmpl.config_step_line_ids.filtered(lambda sl: sl.config_step_id == step)

    def _hide_prints_unless_black(self):
        domain = self.env["product.config.domain"].create({"name": "Black only"})
        self.env["product.config.domain.line"].create({
            "domain_id": domain.id, "attribute_id": self.color.id,
            "value_ids": [(6, 0, self.black.ids)], "condition": "in", "operator": "and",
        })
        self._step_line(self.prints).visibility_domain_id = domain

    # ── LE RANGEMENT ──────────────────────────────────────────────────────

    def test_01_each_question_carries_its_step(self):
        state = self._session().web_state()
        frame, prints = self._step_line(self.frame), self._step_line(self.prints)
        self.assertEqual([s["name"] for s in state["steps"]], ["Frame", "Prints"])
        self.assertEqual(
            {q["name"]: q["stepId"] for q in state["attributes"]},
            {"Color": frame.id, "Plate": frame.id, "Print": prints.id, "Finish": prints.id},
        )

    def test_02_a_line_BEFORE_the_first_step_joins_the_first_step(self):
        """Arbitré par Gerry le 2026-09-30 : pas d'étape implicite « Général »."""
        steps, step_of, _hidden = self._session()._web_step_layout()
        self.assertEqual(step_of[self.lines[self.color].id], steps[0]["id"])

    def test_03_without_steps_the_page_stays_flat(self):
        (self.lines[self.plate] | self.lines[self.print_]).config_step_id = False
        state = self._session().web_state()
        self.assertEqual(state["steps"], [])
        self.assertEqual({q["stepId"] for q in state["attributes"]}, {None})

    # ── UNE ÉTAPE MASQUÉE ─────────────────────────────────────────────────

    def test_04_a_HIDDEN_step_takes_its_questions_away(self):
        """⚠️ D-086 : l'étape masquée n'est pas montrée, ses questions non plus."""
        self._hide_prints_unless_black()
        state = self._session(self.white).web_state()
        self.assertEqual([s["name"] for s in state["steps"]], ["Frame"])
        self.assertEqual([q["name"] for q in state["attributes"]], ["Color", "Plate"])

    def test_05_and_they_are_NOT_required(self):
        self._hide_prints_unless_black()
        session = self._session(self.white | self.carbon)
        self.assertFalse(session._web_missing_attributes())

    def test_06_the_step_comes_back_with_the_answer_that_opens_it(self):
        self._hide_prints_unless_black()
        state = self._session(self.black).web_state()
        self.assertEqual([s["name"] for s in state["steps"]], ["Frame", "Prints"])

    # ── CE QUI MANQUE ─────────────────────────────────────────────────────

    def test_07_missing_answers_are_flagged_on_their_question(self):
        state = self._session(self.white).web_state()
        self.assertEqual(
            {q["name"]: q["missing"] for q in state["attributes"]},
            {"Color": False, "Plate": True, "Print": True, "Finish": True},
        )

    def test_08_missing_answers_come_in_DISPLAY_order(self):
        session = self._session(self.white)
        self.assertEqual(
            session._web_missing_attributes().attribute_id.mapped("name"),
            ["Plate", "Print", "Finish"],
        )

    def test_09_a_required_question_whose_condition_HOLDS_is_required(self):
        """⚠️ Le défaut relevé en préparant D-385 : `_is_visible` recevait un RECORDSET,
        l'intersection avec les identifiants du domaine était toujours vide, et une
        question obligatoire visible par une condition « in » n'était jamais réclamée."""
        domain = self.env["product.config.domain"].create({"name": "Black"})
        self.env["product.config.domain.line"].create({
            "domain_id": domain.id, "attribute_id": self.color.id,
            "value_ids": [(6, 0, self.black.ids)], "condition": "in", "operator": "and",
        })
        self.lines[self.finish].visibility_domain_id = domain
        session = self._session(self.black | self.carbon | self.pla)
        self.assertEqual(session._web_missing_attributes(), self.lines[self.finish])
        # Et Blanc la masque : elle n'est plus exigée.
        session.value_ids = [(6, 0, (self.white | self.carbon | self.pla).ids)]
        self.assertFalse(session._web_missing_attributes())

    # ── LA VUE D'UNE ÉTAPE ────────────────────────────────────────────────

    def test_10_a_step_WITHOUT_a_view_does_not_move_the_camera(self):
        session = self._session()
        steps, _step_of, _hidden = session._web_step_layout()
        step_views, question_views = session._web_views(steps, None)
        served = session._web_steps(steps, step_views)
        self.assertEqual([s["camera"] for s in served], [None, None])
        self.assertEqual(question_views, {})

    def test_11_a_step_view_is_served_in_the_viewer_form(self):
        model3d = self.env["product.model3d"].create(
            {"name": "Drone", "product_tmpl_id": self.tmpl.id}
        )
        view = self.env["product.model3d.camera"].create(
            {"name": "Top", "model3d_id": model3d.id}
        )
        self._step_line(self.prints).view_camera_id = view
        session = self._session()
        steps, _step_of, _hidden = session._web_step_layout()
        step_views, _question_views = session._web_views(steps, None)
        served = {s["name"]: s["camera"] for s in session._web_steps(steps, step_views)}
        self.assertIsNone(served["Frame"])
        self.assertEqual(served["Prints"], session._web_camera_view(view))
        self.assertIn("pose", served["Prints"])

    def test_11b_a_view_carries_its_LIMITS_in_factors(self):
        """D-389 — les bornes partent avec la vue ; la distance en FACTEURS, que le viewer
        convertit avec son propre rayon de référence."""
        model3d = self.env["product.model3d"].create(
            {"name": "Drone", "product_tmpl_id": self.tmpl.id}
        )
        view = self.env["product.model3d.camera"].create({
            "name": "Bornée", "model3d_id": model3d.id,
            "azimuth_min": -40, "azimuth_max": 40,
            "inclination_min": 30, "inclination_max": 80,
            "distance_min": 0.5, "distance_max": 2.0,
        })
        limits = self._session()._web_camera_view(view)["limits"]
        self.assertEqual(limits, {
            "azimuthMin": -40, "azimuthMax": 40,
            "inclinationMin": 30, "inclinationMax": 80,
            "distanceMin": 0.5, "distanceMax": 2.0,
            "distanceIn": "factor",
        })

    def test_12_an_ATTRIBUTE_view_rides_with_its_question(self):
        """D-387 — la page prend la vue de l'attribut quand on ouvre ou répond à sa question."""
        model3d = self.env["product.model3d"].create(
            {"name": "Drone", "product_tmpl_id": self.tmpl.id}
        )
        view = self.env["product.model3d.camera"].create(
            {"name": "Close-up", "model3d_id": model3d.id}
        )
        self.lines[self.plate].view_camera_id = view
        session = self._session()
        questions = {q["name"]: q["camera"] for q in session.web_state()["attributes"]}
        self.assertEqual(questions["Plate"], session._web_camera_view(view))
        self.assertIsNone(questions["Color"])
