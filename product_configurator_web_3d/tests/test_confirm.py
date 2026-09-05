# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""TERMINER une configuration — la boucle qui manquait (2026-09-05).

La page savait poser des questions et montrer un prix ; elle ne savait pas
conclure. Ce qui est éprouvé ici est surtout ce qui doit être REFUSÉ : une
configuration incomplète, et une session qu'on confirmerait deux fois.
"""
import json

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestConfirm(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Value = cls.env["product.attribute.value"]
        cls.couleur = cls.env["product.attribute"].create({"name": "Couleur"})
        cls.blanc, cls.noir = Value.create([
            {"name": "Blanc", "attribute_id": cls.couleur.id},
            {"name": "Noir", "attribute_id": cls.couleur.id},
        ])
        cls.serrure = cls.env["product.attribute"].create({"name": "Serrure"})
        cls.trois_points = Value.create(
            {"name": "Trois points", "attribute_id": cls.serrure.id}
        )
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte a terminer",
            "config_ok": True,
            "list_price": 100.0,
            "attribute_line_ids": [
                Command.create({
                    "attribute_id": cls.couleur.id,
                    "value_ids": [Command.set((cls.blanc | cls.noir).ids)],
                    "required": True,
                }),
                Command.create({
                    "attribute_id": cls.serrure.id,
                    "value_ids": [Command.set(cls.trois_points.ids)],
                    "required": True,
                }),
            ],
        })

    def _session(self, values):
        session = self.env["product.config.session"].create_get_session(
            self.tmpl.id, force_create=True
        )
        session.value_ids = [(6, 0, values.ids)]
        session._ensure_access_token()
        return session

    def _call(self, route, **params):
        response = self.url_open(
            route,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
            headers={"Content-Type": "application/json"},
        )
        return response.json().get("result")

    # ── CE QUI DOIT ÊTRE REFUSÉ ──────────────────────────────────────────

    def test_sans_jeton_rien(self):
        self.assertEqual(self._call("/configurator/confirm"),
                         {"error": "unknown_session"})

    def test_une_configuration_incomplete_est_REFUSEE_et_dit_ce_qui_manque(self):
        session = self._session(self.blanc)
        result = self._call("/configurator/confirm", token=session.access_token)
        self.assertEqual(result["error"], "incomplete")
        # ⓘ Les NOMS : « configuration incomplète » n'aide personne sur un
        # produit qui pose quinze questions.
        self.assertEqual(result["missing"], ["Serrure"])
        self.assertEqual(session.state, "draft")
        self.assertFalse(session.product_id)

    def test_une_session_deja_confirmee_ne_se_re_confirme_pas(self):
        session = self._session(self.blanc | self.trois_points)
        self._call("/configurator/confirm", token=session.access_token)
        encore = self._call("/configurator/confirm", token=session.access_token)
        self.assertEqual(encore, {"error": "session_closed"})

    def test_une_session_confirmee_ne_se_MODIFIE_plus(self):
        """La variante est née ; changer la configuration sous elle serait pire
        qu'un refus."""
        session = self._session(self.blanc | self.trois_points)
        self._call("/configurator/confirm", token=session.access_token)
        result = self._call(
            "/configurator/set_value", token=session.access_token,
            attribute_id=self.couleur.id, value_id=self.noir.id,
        )
        self.assertEqual(result, {"error": "session_closed"})
        self.assertIn(self.blanc, session.value_ids)

    # ── ET CE QUI DOIT ARRIVER ───────────────────────────────────────────

    def test_terminer_ferme_la_session_et_FAIT_NAITRE_la_variante(self):
        session = self._session(self.blanc | self.trois_points)
        state = self._call("/configurator/confirm", token=session.access_token)
        self.assertEqual(session.state, "done")
        self.assertTrue(session.product_id)
        self.assertEqual(session.product_id.product_tmpl_id, self.tmpl)
        # La page reçoit l'état, pas un accusé de réception : c'est ce qui lui
        # permet d'afficher la fermeture sans un aller-retour de plus.
        self.assertEqual(state["state"], "done")
        self.assertNotIn("error", state)

    def test_un_attribut_MASQUE_n_empeche_pas_de_terminer(self):
        """⚠️ D-086 : la visibilité passe AVANT l'exigence. Une question que le
        client ne voit pas ne peut pas le bloquer."""
        ligne_serrure = self.tmpl.attribute_line_ids.filtered(
            lambda line: line.attribute_id == self.serrure
        )
        domaine = self.env["product.config.domain"].create({"name": "Jamais"})
        self.env["product.config.domain.line"].create({
            "domain_id": domaine.id,
            "attribute_id": self.couleur.id,
            "value_ids": [(6, 0, self.noir.ids)],
            "condition": "in",
            "operator": "and",
        })
        ligne_serrure.visibility_domain_id = domaine
        session = self._session(self.blanc)  # Blanc : la serrure est masquée
        state = self._call("/configurator/confirm", token=session.access_token)
        self.assertNotIn("error", state)
        self.assertEqual(session.state, "done")
