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

    def test_une_modification_DIFFUSE_l_etat_complet(self):
        """⚠️ L'état complet, pas un delta : c'est ce que la page sait déjà
        appliquer, avec le code qu'elle a — donc rien de neuf à écrire côté
        client, et rien qui puisse diverger de `/configurator/state`."""
        envois = []
        with patch.object(
            type(self.session), "_bus_send",
            lambda records, kind, message, **kw: envois.append((kind, message)),
        ):
            self.session.write({"value_ids": [(6, 0, self.noir.ids)]})
        self.assertEqual(len(envois), 1)
        kind, message = envois[0]
        self.assertEqual(kind, "configurator_state")
        self.assertEqual(message["productName"], self.tmpl.display_name)
        self.assertIn("attributes", message)
        # ⓘ Le jeton n'est PAS dans ce qui circule — il entre, il ne sort pas.
        self.assertNotIn(self.session.access_token, str(message))

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
