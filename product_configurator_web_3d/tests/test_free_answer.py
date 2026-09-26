# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La SAISIE LIBRE sur la page du configurateur — D-353.

Une question dont la ligne autorise l'ajout se répond dans un champ, texte ou nombre.
Ce qui est éprouvé : la page reçoit la forme du champ ; la saisie se RANGE dans la
session et n'y devient une valeur qu'à la confirmation ; elle atteint la 3D, le contrôle
des questions obligatoires et la confirmation ; une saisie qui désigne une valeur offerte
est un CHOIX. Ce qui doit être REFUSÉ : une saisie hors bornes, et une saisie sur une
question qui ne l'accepte pas — au serveur, puisque la route est publique.
"""
import json

from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged


class FreeAnswerCommon:
    @classmethod
    def _fixture(cls):
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.Value = Value
        mm = cls.env.ref("uom.product_uom_millimeter")
        cls.width = Attribute.create({
            "name": "Largeur", "val_custom": True, "custom_type": "float",
            "uom_id": mm.id, "create_variant": "dynamic",
        })
        cls.w150, cls.w200 = Value.create([
            {"name": "150", "attribute_id": cls.width.id},
            {"name": "200", "attribute_id": cls.width.id},
        ])
        cls.dedication = Attribute.create({
            "name": "Dédicace", "val_custom": True, "custom_type": "char",
            "create_variant": "no_variant",
        })
        cls.colour = Attribute.create({"name": "Couleur", "create_variant": "dynamic"})
        cls.white = Value.create({"name": "Blanc", "attribute_id": cls.colour.id})
        cls.tmpl = cls.env["product.template"].create({
            "name": "Caisse à saisir",
            "config_ok": True,
            "attribute_line_ids": [
                Command.create({
                    "attribute_id": cls.width.id,
                    "value_ids": [Command.set((cls.w150 | cls.w200).ids)],
                    "custom": True, "required": True,
                    "has_min_val": True, "min_val": 100,
                    "has_max_val": True, "max_val": 600,
                }),
                Command.create({
                    "attribute_id": cls.dedication.id,
                    "custom": True, "required": False, "max_length": 12,
                }),
                Command.create({
                    "attribute_id": cls.colour.id,
                    "value_ids": [Command.set(cls.white.ids)],
                    "required": True,
                }),
            ],
        })

    def _new_session(self):
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
        })
        session.value_ids = [(6, 0, self.white.ids)]
        return session

    @staticmethod
    def _question(state, attribute):
        return next(q for q in state["attributes"] if q["id"] == attribute.id)


@tagged("post_install", "-at_install")
class TestFreeAnswer(FreeAnswerCommon, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()

    def setUp(self):
        super().setUp()
        self.session = self._new_session()

    # ── LA FORME DU CHAMP ARRIVE ────────────────────────────────────────────

    def test_la_question_avec_ajout_porte_son_champ(self):
        question = self._question(self.session.web_state(), self.width)
        self.assertEqual(question["free"], {
            "numeric": True, "unit": "mm", "min": 100.0, "max": 600.0,
            "step": None, "maxLength": None, "regexp": None,
        })
        texte = self._question(self.session.web_state(), self.dedication)["free"]
        self.assertEqual((texte["numeric"], texte["maxLength"]), (False, 12))

    def test_la_question_sans_ajout_n_a_que_sa_liste(self):
        self.assertIsNone(self._question(self.session.web_state(), self.colour)["free"])

    def test_la_valeur_CUSTOM_d_OCA_n_est_plus_une_reponse(self):
        """Relevé le 2026-09-25 : un bouton « Custom » sur chaque question de la Caisse,
        valeur d'un AUTRE attribut, qu'on ne pouvait que refuser."""
        custom = self.session.get_custom_value_id()
        for question in self.session.web_state()["attributes"]:
            self.assertNotIn(custom.id, [v["id"] for v in question["values"]])

    # ── RÉPONDRE PAR SAISIE ─────────────────────────────────────────────────

    def test_la_saisie_se_range_dans_la_SESSION_pas_au_catalogue(self):
        before = self.Value.search_count([("attribute_id", "=", self.width.id)])
        state = self.session.web_set_custom_value(self.width.id, "480,5")
        self.assertEqual(self.session.custom_value_ids.value, "480.5")
        self.assertEqual(
            self.Value.search_count([("attribute_id", "=", self.width.id)]), before,
            "la valeur ne naît qu'à la confirmation (Gerry, 2026-09-25)")
        question = self._question(state, self.width)
        self.assertEqual(question["customValue"], "480.5")
        self.assertFalse([v for v in question["values"] if v["chosen"]],
                         "une saisie n'est pas une valeur cochée")

    def test_la_saisie_atteint_la_3D(self):
        self.session.web_set_custom_value(self.width.id, "480")
        self.assertEqual(self.session._web_values()[self.width.id], "480")

    def test_l_unite_tapee_par_habitude_est_toleree(self):
        self.session.web_set_custom_value(self.width.id, "480 mm")
        self.assertEqual(self.session.custom_value_ids.value, "480")

    def test_une_saisie_qui_designe_une_valeur_OFFERTE_est_un_choix(self):
        self.session.web_set_custom_value(self.width.id, "200,0")
        self.assertIn(self.w200, self.session.value_ids)
        self.assertFalse(self.session.custom_value_ids)

    def test_choisir_apres_avoir_tape_efface_la_saisie(self):
        self.session.web_set_custom_value(self.width.id, "480")
        self.session.web_set_custom_value(self.width.id, "150")
        self.assertFalse(self.session.custom_value_ids)
        self.assertIn(self.w150, self.session.value_ids)

    def test_une_saisie_VIDE_efface_la_reponse_tapee(self):
        self.session.web_set_custom_value(self.dedication.id, "Pour Paul")
        self.session.web_set_custom_value(self.dedication.id, "   ")
        self.assertFalse(self.session.custom_value_ids)

    # ── CE QUI EST REFUSÉ, AU SERVEUR ───────────────────────────────────────

    def test_hors_bornes_est_REFUSE_avec_un_message(self):
        result = self.session.web_set_custom_value(self.width.id, "900")
        self.assertEqual(result["error"], "invalid_custom")
        self.assertIn("above the maximum", result["message"])
        self.assertFalse(self.session.custom_value_ids)

    def test_un_texte_trop_long_est_REFUSE(self):
        result = self.session.web_set_custom_value(self.dedication.id, "x" * 13)
        self.assertEqual(result["error"], "invalid_custom")

    def test_une_question_sans_ajout_refuse_la_saisie(self):
        self.assertEqual(self.session.web_set_custom_value(self.colour.id, "Rouge"),
                         {"error": "custom_not_allowed"})

    def test_une_question_MULTIPLE_refuse_la_saisie_en_v1(self):
        self.tmpl.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.dedication).multi = True
        self.assertEqual(self.session.web_set_custom_value(self.dedication.id, "Paul"),
                         {"error": "custom_not_allowed"})

    # ── TERMINER ────────────────────────────────────────────────────────────

    def test_une_question_obligatoire_repondue_par_saisie_n_est_pas_manquante(self):
        self.session.value_ids = [(6, 0, self.white.ids)]
        self.session.web_set_custom_value(self.width.id, "480")
        self.assertFalse(self.session._web_missing_attributes())

    def test_a_la_confirmation_la_saisie_devient_une_valeur_de_la_variante(self):
        self.session.web_set_custom_value(self.width.id, "480")
        self.session.web_set_custom_value(self.dedication.id, "Pour Paul")
        self.session.web_confirm()
        variant = self.session.product_id
        names = variant.product_template_attribute_value_ids.mapped("name")
        self.assertIn("480", names)
        self.assertFalse(
            self.Value.search([("attribute_id", "=", self.dedication.id)]),
            "une dédicace (`no_variant`) ne devient pas un article")
        self.assertIn("Pour Paul", self.session.custom_value_ids.mapped("value"))


@tagged("post_install", "-at_install")
class TestFreeAnswerPlacement(TransactionCase):
    """La saisie d'une pièce POSÉE — D-332 + D-353 (arbitrage 1 : un enfant dont une
    question autorise l'ajout a la saisie)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        cls.length = Attribute.create({
            "name": "Longueur de poignée", "val_custom": True, "custom_type": "float",
            "create_variant": "dynamic",
        })
        cls.l100 = cls.env["product.attribute.value"].create(
            {"name": "100", "attribute_id": cls.length.id})
        cls.handle_tmpl = cls.env["product.template"].create({
            "name": "Poignée longue",
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.length.id,
                "value_ids": [Command.set(cls.l100.ids)],
                "custom": True,
            })],
        })
        Model3d = cls.env["product.model3d"]
        handle = Model3d.create({"name": "Poignée", "product_tmpl_id": cls.handle_tmpl.id})
        door_tmpl = cls.env["product.template"].create({"name": "Porte", "config_ok": True})
        door = Model3d.create({
            "name": "Porte", "product_tmpl_id": door_tmpl.id, "piece_type": "assembly",
        })
        cls.link = cls.env["product.model3d.component"].create(
            {"parent_id": door.id, "child_id": handle.id})
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": door_tmpl.id, "user_id": cls.env.user.id,
        })

    def _question(self, state):
        placement = state["placements"]["c%s" % self.link.id]
        return placement["questions"][0]

    def test_la_question_d_un_placement_porte_son_champ(self):
        self.assertTrue(self._question(self.session.web_state())["free"]["numeric"])

    def test_la_saisie_d_un_placement_se_range_par_lien_et_entre_dans_la_definition(self):
        state = self.session.web_set_custom_value(self.length.id, "135", link_id=self.link.id)
        self.assertEqual(self.session.child_custom_values,
                         {str(self.link.id): {str(self.length.id): "135"}})
        self.assertEqual(self._question(state)["customValue"], "135")
        child = next(c for c in state["definition"]["children"]
                     if c["linkId"] == self.link.id)
        # ⓘ La définition porte le NOMBRE — ce que la portée du moteur compare (D-160).
        self.assertEqual(child["attributeOverrides"][str(self.length.id)], {"value": 135.0})

    def test_la_saisie_d_un_placement_ne_coche_pas_le_defaut(self):
        state = self.session.web_set_custom_value(self.length.id, "135", link_id=self.link.id)
        self.assertFalse([v for v in self._question(state)["values"] if v["chosen"]])

    def test_a_la_confirmation_la_variante_de_l_enfant_porte_la_saisie(self):
        self.session.web_set_custom_value(self.length.id, "135", link_id=self.link.id)
        self.session.web_confirm()
        variant = self.env["product.product"].browse(
            self.session.child_variants[str(self.link.id)])
        self.assertEqual(variant.product_template_attribute_value_ids.mapped("name"), ["135"])


@tagged("post_install", "-at_install")
class TestFreeAnswerRoute(FreeAnswerCommon, HttpCase):
    """La ROUTE publique aiguille — elle ne décide de rien."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()

    def _call(self, route, **params):
        response = self.url_open(
            route,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
            headers={"Content-Type": "application/json"},
        )
        return response.json().get("result")

    def test_la_saisie_passe_par_set_value(self):
        session = self._new_session()
        session._ensure_access_token()
        state = self._call("/configurator/set_value", token=session.access_token,
                           attribute_id=self.width.id, custom_value="480")
        self.assertEqual(self._question(state, self.width)["customValue"], "480")

    def test_un_refus_revient_avec_son_message(self):
        session = self._new_session()
        session._ensure_access_token()
        result = self._call("/configurator/set_value", token=session.access_token,
                            attribute_id=self.width.id, custom_value="9000")
        self.assertEqual(result["error"], "invalid_custom")
        self.assertTrue(result["message"])
