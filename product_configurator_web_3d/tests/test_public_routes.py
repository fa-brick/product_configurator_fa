# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Les routes publiques de la configuration — D-091, D-190, lot 6 blocage n° 3.

Ce qui est éprouvé ici est surtout ce qui doit être REFUSÉ : sans cela, un jeton
de 32 octets ne protège rien. Et une chose qui doit **ne pas** arriver — la
fourche à chaque clic, qui ferait perdre sa configuration au visiteur.
"""
import json

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPublicRoutes(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.attribute = Attribute.create({"name": "Couleur"})
        cls.blanc, cls.noir = Value.create([
            {"name": "Blanc", "attribute_id": cls.attribute.id},
            {"name": "Noir", "attribute_id": cls.attribute.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte configurable",
            "config_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id,
                "value_ids": [Command.set((cls.blanc | cls.noir).ids)],
            })],
        })
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": cls.tmpl.id,
            "user_id": cls.env.user.id,
            "value_ids": [Command.set(cls.blanc.ids)],
        })

    def _call(self, route, **params):
        """Un appel JSON-RPC anonyme — comme un visiteur, sans session web."""
        response = self.url_open(
            route,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
            headers={"Content-Type": "application/json"},
        )
        return response.json().get("result")

    # ── CE QUI DOIT ÊTRE REFUSÉ ──────────────────────────────────────────

    def test_sans_jeton_rien(self):
        self.assertEqual(self._call("/configurator/state"),
                         {"error": "unknown_session"})

    def test_un_jeton_inconnu_ne_dit_pas_qu_il_est_inconnu(self):
        """⚠️ Même réponse qu'un jeton absent : distinguer « inconnu » de
        « périmé » dirait à qui tâtonne quels jetons ont existé."""
        self.assertEqual(self._call("/configurator/state", token="x" * 32),
                         {"error": "unknown_session"})

    def test_le_NUMÉRO_de_session_ne_vaut_pas_jeton(self):
        """⚠️ `CS0001` est une séquence énumérable — c'est tout le motif de D-091."""
        self.assertEqual(self._call("/configurator/state",
                                    token=self.session.name),
                         {"error": "unknown_session"})

    def test_une_session_ARCHIVÉE_ne_répond_plus(self):
        self.session.active = False
        self.assertEqual(self._call("/configurator/state",
                                    token=self.session.access_token),
                         {"error": "unknown_session"})

    def test_une_session_CONFIRMÉE_ne_se_modifie_plus(self):
        """Elle a donné sa variante : la changer sous une commande passée serait
        pire qu'un refus."""
        self.session.action_confirm()
        out = self._call("/configurator/set_value",
                         token=self.session.access_token,
                         attribute_id=self.attribute.id, value_id=self.noir.id)
        self.assertEqual(out, {"error": "session_closed"})

    def test_une_valeur_d_une_AUTRE_question_est_refusée(self):
        autre = self.env["product.attribute.value"].create({
            "name": "Chêne",
            "attribute_id": self.env["product.attribute"].create({"name": "Bois"}).id,
        })
        out = self._call("/configurator/set_value",
                         token=self.session.access_token,
                         attribute_id=self.attribute.id, value_id=autre.id)
        self.assertEqual(out, {"error": "unknown_value"})

    # ── CE QUI DOIT MARCHER ──────────────────────────────────────────────

    def test_un_jeton_valide_rend_SA_configuration(self):
        state = self._call("/configurator/state", token=self.session.access_token)
        self.assertEqual(state["productName"], "Porte configurable")
        self.assertEqual(len(state["attributes"]), 1)
        choisies = [v["name"] for v in state["attributes"][0]["values"] if v["chosen"]]
        self.assertEqual(choisies, ["Blanc"])

    def test_les_valeurs_INDISPONIBLES_sont_rendues_marquées(self):
        """⚠️ On les grise, on ne les cache pas (D-168) — et un appui dira
        pourquoi (D-178). Les retirer ici ôterait à la page le moyen de le dire."""
        state = self._call("/configurator/state", token=self.session.access_token)
        for value in state["attributes"][0]["values"]:
            self.assertIn("available", value)

    def test_répondre_change_la_configuration_et_rend_l_état(self):
        state = self._call("/configurator/set_value",
                           token=self.session.access_token,
                           attribute_id=self.attribute.id, value_id=self.noir.id)
        choisies = [v["name"] for v in state["attributes"][0]["values"] if v["chosen"]]
        self.assertEqual(choisies, ["Noir"])
        self.assertEqual(self.session.value_ids, self.noir)

    def test_repondre_NE_FORKE_PAS_la_session(self):
        """D-190 — le porteur du jeton EST le propriétaire.

        `_session_for_edit` duplique quand l'utilisateur courant n'est pas le
        propriétaire : c'est juste au back-office, où un commercial reprend la
        configuration d'un autre. Ici l'appelant est TOUJOURS l'utilisateur
        public — forker à chaque clic créerait une session par réponse, et le
        visiteur perdrait la sienne au premier changement.
        """
        avant = self.env["product.config.session"].search_count([])
        self._call("/configurator/set_value", token=self.session.access_token,
                   attribute_id=self.attribute.id, value_id=self.noir.id)
        self.assertEqual(self.env["product.config.session"].search_count([]), avant)
        self.assertFalse(self.session.child_ids)

    def test_le_jeton_ne_RESSORT_pas_de_la_réponse(self):
        """Une page publique ne doit rien laisser filtrer qui permette d'énumérer."""
        state = self._call("/configurator/state", token=self.session.access_token)
        brut = json.dumps(state)
        self.assertNotIn(self.session.access_token, brut)
        self.assertNotIn(self.session.name, brut)

    # ── LA PAGE (lot 6) ──────────────────────────────────────────────────

    def test_la_page_se_rend_pour_un_visiteur_anonyme(self):
        """Elle est NUE : `web.frontend_layout`, sans `website` — et elle porte le
        point de montage du composant."""
        page = self.url_open(f"/configurator/{self.session.access_token}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("product_configurator_web_3d.ConfiguratorPage", page.text)

    def test_la_page_charge_le_bundle_qui_porte_le_VIEWER(self):
        """⚠️ Sans `web.assets_frontend`, la page s'afficherait — vide. C'est le
        blocage n° 2 du lot 6, et il se vérifie ici de bout en bout."""
        page = self.url_open(f"/configurator/{self.session.access_token}")
        self.assertIn("assets_frontend", page.text)

    def test_un_jeton_inconnu_rend_QUAND_MÊME_la_page(self):
        """⚠️ Délibéré (D-190) : c'est l'appel d'état qui dira que le lien ne vaut
        rien. Un 404 ici dirait à qui tâtonne QUELS JETONS EXISTENT."""
        page = self.url_open("/configurator/" + "z" * 32)
        self.assertEqual(page.status_code, 200)

    def test_le_jeton_voyage_en_PROP_et_nulle_part_ailleurs(self):
        page = self.url_open(f"/configurator/{self.session.access_token}")
        # Il est dans le prop du composant — c'est ainsi qu'il entre — et la page ne
        # porte ni le numéro de session ni un autre jeton.
        self.assertIn(self.session.access_token, page.text)
        self.assertNotIn(self.session.name, page.text)
