# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Voir la configuration d'un autre EN DIRECT — D-253.

Deux choses à éprouver, et elles se répondent : ce qui part sur le fil quand
une configuration change, et qui a le droit de l'écouter.
"""
from unittest.mock import patch

from odoo import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.product_configurator_web_3d.models.ir_websocket import CHANNEL_PREFIX


@tagged("post_install", "-at_install")
class TestLive(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create({"name": "Couleur"})
        cls.blanc, cls.noir = cls.env["product.attribute.value"].create([
            {"name": "Blanc", "attribute_id": cls.attribute.id},
            {"name": "Noir", "attribute_id": cls.attribute.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte partagee",
            "config_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id,
                "value_ids": [Command.set((cls.blanc | cls.noir).ids)],
            })],
        })
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": cls.tmpl.id,
            "user_id": cls.env.user.id,
        })
        cls.session._ensure_access_token()

    # ── CE QUI PART SUR LE FIL ───────────────────────────────────────────

    def test_une_modification_DIFFUSE_un_SIGNAL_et_non_l_etat(self):
        """⚠️ Un signal, plus l'état complet (L-451) : le message portait tout
        `web_state()` — environ 500 Ko sur le JeNo —, calculé une seconde fois dans
        le `write` et rangé dans `bus_bus` à chaque clic. Les spectateurs relisent
        `/configurator/state`."""
        envois = []
        with patch.object(
            type(self.session), "_bus_send",
            lambda records, kind, message, **kw: envois.append((kind, message)),
        ), patch.object(
            type(self.session), "web_state",
            side_effect=AssertionError("web_state ne doit plus être calculé pour le bus"),
        ):
            self.session.write({"value_ids": [(6, 0, self.noir.ids)]})
        self.assertEqual(envois, [("configurator_state", {"author": None})])

    def test_le_signal_NOMME_l_auteur_que_la_route_a_pose(self):
        """L'onglet qui a agi ignore son propre signal : il a déjà l'état en réponse.
        ⓘ Le porteur n'est pas un secret (voir `_hand_state`) ; le jeton d'accès, si."""
        envois = []
        with patch.object(
            type(self.session), "_bus_send",
            lambda records, kind, message, **kw: envois.append(message),
        ):
            self.session.with_context(cfg_author="onglet-1").write(
                {"value_ids": [(6, 0, self.noir.ids)]})
        self.assertEqual(envois, [{"author": "onglet-1"}])
        self.assertNotIn(self.session.access_token, str(envois))

    def test_une_ecriture_qui_ne_CHANGE_rien_ne_diffuse_rien(self):
        self.session.write({"value_ids": [(6, 0, self.blanc.ids)]})
        envois = []
        with patch.object(
            type(self.session), "_bus_send",
            lambda records, kind, message, **kw: envois.append(kind),
        ):
            self.session.write({"value_ids": [(6, 0, self.blanc.ids)]})
            self.session.write({"name": self.session.name})
        self.assertEqual(envois, [])

    # ── QUI A LE DROIT D'ÉCOUTER ─────────────────────────────────────────

    def test_le_JETON_ouvre_le_canal(self):
        canaux = self.env["ir.websocket"]._configurator_channel_list(
            [f"{CHANNEL_PREFIX}{self.session.access_token}"]
        )
        self.assertIn(self.session, canaux)
        # ⚠️ La chaîne d'origine ne DOIT pas subsister : elle porte le jeton, et
        # un canal est un identifiant partagé.
        self.assertNotIn(
            f"{CHANNEL_PREFIX}{self.session.access_token}", canaux
        )

    def test_un_jeton_inconnu_n_ouvre_RIEN(self):
        canaux = self.env["ir.websocket"]._configurator_channel_list(
            [f"{CHANNEL_PREFIX}{'x' * 32}"]
        )
        self.assertNotIn(self.session, canaux)

    def test_les_autres_canaux_traversent_intacts(self):
        """⚠️ On ne doit pas manger ce qui ne nous est pas destiné : les autres
        modules lisent la même liste après nous."""
        canaux = self.env["ir.websocket"]._configurator_channel_list(["un_autre_canal"])
        self.assertIn("un_autre_canal", canaux)
