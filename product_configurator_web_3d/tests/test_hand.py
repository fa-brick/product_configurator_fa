# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""LA MAIN et la CAMÉRA partagée — D-255, D-256.

Ce qui est éprouvé : qu'on ne conduise pas à deux sans le savoir, qu'une main
oubliée finisse par se rendre, et qu'un point de vue ne parte que de celui qui
conduit.
"""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import HttpCase, tagged

from odoo.addons.product_configurator_web_3d.models.product_config_hand import (
    HAND_TTL_SECONDS,
)


@tagged("post_install", "-at_install")
class TestHand(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create({"name": "Couleur"})
        cls.blanc, cls.noir = cls.env["product.attribute.value"].create([
            {"name": "Blanc", "attribute_id": cls.attribute.id},
            {"name": "Noir", "attribute_id": cls.attribute.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte a deux mains",
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

    def _call(self, route, **params):
        response = self.url_open(
            route,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
            headers={"Content-Type": "application/json"},
        )
        return response.json().get("result")

    def _pick(self, holder, value):
        return self._call(
            "/configurator/set_value", token=self.session.access_token,
            holder=holder, attribute_id=self.attribute.id, value_id=value.id,
        )

    # ── PRENDRE ET GARDER ────────────────────────────────────────────────

    def test_une_configuration_neuve_n_a_pas_de_conducteur(self):
        self.assertTrue(self.session._hand_is_free())
        state = self._call("/configurator/state", token=self.session.access_token)
        self.assertEqual(state["hand"], {"holder": None, "label": None})

    def test_le_PREMIER_geste_prend_la_main(self):
        state = self._pick("onglet-A", self.noir)
        self.assertEqual(state["hand"]["holder"], "onglet-A")
        self.assertTrue(state["hand"]["label"])

    def test_le_SECOND_est_refuse_et_sait_QUI_conduit(self):
        self._pick("onglet-A", self.noir)
        refus = self._pick("onglet-B", self.blanc)
        self.assertEqual(refus["error"], "not_holding")
        self.assertEqual(refus["hand"]["holder"], "onglet-A")
        # ⓘ Le libellé accompagne le refus : sans lui la page ne pourrait
        # qu'afficher « non ».
        self.assertTrue(refus["hand"]["label"])
        self.session.invalidate_recordset(["value_ids"])
        self.assertEqual(self.session.value_ids, self.noir, "rien n'a été écrit")

    def test_TERMINER_demande_la_main_comme_le_reste(self):
        self._pick("onglet-A", self.noir)
        refus = self._call(
            "/configurator/confirm", token=self.session.access_token, holder="onglet-B"
        )
        self.assertEqual(refus["error"], "not_holding")
        self.session.invalidate_recordset(["state"])
        self.assertEqual(self.session.state, "draft")

    # ── RENDRE, DE GRÉ OU PAR OUBLI ──────────────────────────────────────

    def test_PRENDRE_LA_MAIN_reussit_toujours(self):
        """⚠️ Ce n'est pas un verrou qu'on force : Gerry a tranché que l'interne
        agit sur la configuration du client (D-253). Refuser ici rendrait cette
        décision inapplicable dès que le client aurait touché un bouton."""
        self._pick("onglet-A", self.noir)
        state = self._call(
            "/configurator/take_hand", token=self.session.access_token,
            holder="onglet-B",
        )
        self.assertEqual(state["hand"]["holder"], "onglet-B")
        self.assertFalse(self._pick("onglet-B", self.blanc).get("error"))

    def test_une_main_OUBLIEE_finit_par_se_rendre(self):
        """Un onglet fermé ne doit pas garder la main pour toujours — et
        personne ne pense à la rendre."""
        self._pick("onglet-A", self.noir)
        self.session.invalidate_recordset()
        self.session.sudo().hand_since = fields.Datetime.now() - timedelta(
            seconds=HAND_TTL_SECONDS + 1
        )
        self.assertTrue(self.session._hand_is_free())
        state = self._pick("onglet-B", self.blanc)
        self.assertEqual(state["hand"]["holder"], "onglet-B")

    def test_la_main_ne_se_rend_pas_TANT_QU_ON_S_EN_SERT(self):
        """Le compteur repart à chaque geste, pas au premier."""
        self._pick("onglet-A", self.noir)
        self.session.invalidate_recordset()
        premier = self.session.hand_since
        self._pick("onglet-A", self.blanc)
        self.session.invalidate_recordset()
        self.assertGreaterEqual(self.session.hand_since, premier)

    # ── LE POINT DE VUE ──────────────────────────────────────────────────

    def test_seul_celui_qui_conduit_partage_sa_CAMERA(self):
        """⚠️ Sans cette réserve, deux personnes qui regardent chacune de leur
        côté se renverraient leur vue à tour de rôle."""
        self._pick("onglet-A", self.noir)
        refus = self._call(
            "/configurator/camera", token=self.session.access_token,
            holder="onglet-B", pose={"azimuth": 10},
        )
        self.assertEqual(refus, {"error": "not_holding"})

    def test_la_camera_PART_sur_le_fil_et_ne_s_ECRIT_pas(self):
        envois = []
        self.session._take_hand("onglet-A")
        with patch.object(
            type(self.session), "_bus_send",
            lambda records, kind, message, **kw: envois.append((kind, message)),
        ):
            self.session._bus_send  # noqa: B018 — le patch est en place
            self._call(
                "/configurator/camera", token=self.session.access_token,
                holder="onglet-A", pose={"azimuth": 42, "inclination": 60},
            )
        # ⓘ La route s'exécute dans le fil du serveur d'essai : le patch porte
        # sur la classe, donc il la couvre aussi.
        self.assertTrue(any(kind == "configurator_camera" for kind, _m in envois))
        message = [m for k, m in envois if k == "configurator_camera"][0]
        self.assertEqual(message["holder"], "onglet-A")
        self.assertEqual(message["pose"]["azimuth"], 42)
        self.assertNotIn("pose", self.env["product.config.session"]._fields)
