# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""L'image d'une variante NÉE d'une configuration — D-399, lot 5 (voie A).

Ce qui compte surtout, c'est ce qui est REFUSÉ : la route est publique, et la variante est
PARTAGÉE entre tous les clients d'une même combinaison. On n'écrit que sur une variante que
CETTE confirmation a créée (ou qui n'a aucune image), jamais par-dessus l'éditeur, et
seulement un vrai PNG de 1024 px au plus.
"""
import base64
import io
import json

from PIL import Image

from odoo import Command
from odoo.tests import HttpCase, tagged


def png(width=4, height=4):
    out = io.BytesIO()
    Image.new("RGB", (width, height), (200, 120, 40)).save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode()


@tagged("post_install", "-at_install")
class TestVariantImageD399(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Value = cls.env["product.attribute.value"]
        # ⓘ `dynamic` : la variante NAÎT à la confirmation — le cas de la voie A.
        cls.size = cls.env["product.attribute"].create(
            {"name": "Taille D-399 page", "create_variant": "dynamic"})
        cls.small, cls.large = Value.create([
            {"name": "30", "attribute_id": cls.size.id},
            {"name": "60", "attribute_id": cls.size.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Étagère page D-399",
            "config_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.size.id,
                "value_ids": [Command.set((cls.small | cls.large).ids)],
                "required": True,
            })],
        })
        cls.model3d = cls.env["product.model3d"].create({
            "name": "Étagère page D-399", "product_tmpl_id": cls.tmpl.id,
            "preview_backdrop": "studio", "preview_bg_color": "#FFFFFF",
        })
        cls.camera = cls.env["product.model3d.camera"].create({
            "model3d_id": cls.model3d.id, "name": "Vue D-399", "is_thumbnail": True,
            "shadow_back_wall": True,
        })

    def _session(self, values):
        session = self.env["product.config.session"].create_get_session(
            self.tmpl.id, force_create=True)
        session.value_ids = [(6, 0, values.ids)]
        session._ensure_access_token()
        return session

    def _call(self, route, **params):
        response = self.url_open(
            route,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
            headers={"Content-Type": "application/json"},
        )
        # ⓘ La route écrit dans un AUTRE environnement : le cache de celui du test garderait
        # les valeurs d'avant (`variant_created` posé à faux à la création de la session).
        self.env.invalidate_all()
        return response.json().get("result")

    def _confirm(self, values):
        session = self._session(values)
        state = self._call("/configurator/confirm", token=session.access_token)
        self.assertEqual(state.get("state"), "done", state)
        return session, state

    # ── La prise de vue que la page reçoit ──────────────────────────────

    def test_a_created_variant_asks_for_its_picture(self):
        """La confirmation CRÉE la variante : l'état porte la prise de vue à rejouer."""
        # ⚠️ La Taille 60 et non 30 : l'éditeur 3D CRÉE la variante PAR DÉFAUT à la
        # création du modèle (`_ensure_default_variant_for_the_3d_editor`) — confirmer la 30
        # la retrouverait, et c'est juste.
        session, state = self._confirm(self.large)
        self.assertTrue(session.variant_created)
        photo = state["photo"]
        self.assertEqual(photo["backdrop"], "studio")
        self.assertEqual(photo["surfaces"], {"floor": True, "backWall": True, "sideWall": False})
        self.assertIn("pose", photo)
        self.assertEqual(photo["size"], 1024)
        # Pas de passe encore : pas de cadre commun à rejouer.
        self.assertIsNone(photo["framing"])

    def test_the_default_variant_is_found_not_created(self):
        """La variante par défaut existe déjà (l'éditeur la crée) : trouvée, pas créée — et,
        tant qu'elle n'a pas d'image, la page la photographie quand même."""
        session, state = self._confirm(self.small)
        self.assertFalse(session.variant_created)
        self.assertIsNotNone(state["photo"])

    def test_the_common_frame_of_the_last_pass_is_served(self):
        """Le cadre gardé par la dernière passe de l'éditeur est rejoué par la page."""
        self.camera.write({"variant_frame_radius": 900.0,
                           "variant_frame_center": '{"centre": [1, 2, 3], "halfHeight": 50}'})
        _session, state = self._confirm(self.large)
        self.assertEqual(state["photo"]["framing"], {
            "mode": "fixed", "centre": {"x": 1, "y": 2, "z": 3},
            "radius": 900.0, "halfHeight": 50,
        })

    def test_no_permission_no_picture(self):
        """Sans `preview_managed`, la page ne photographie rien."""
        self.model3d.preview_managed = False
        _session, state = self._confirm(self.small)
        self.assertIsNone(state["photo"])

    # ── L'image envoyée ─────────────────────────────────────────────────

    def test_the_picture_is_stored_as_the_customers(self):
        """Une image valide sur la variante créée : écrite, et marquée « client »."""
        session, _state = self._confirm(self.small)
        result = self._call("/configurator/variant_image", token=session.access_token,
                            product_id=session.product_id.id, image=png())
        self.assertEqual(result, {"ok": True})
        self.assertTrue(session.product_id.image_variant_1920)
        self.assertEqual(session.product_id.editor_image_source, "client")

    def test_unknown_token_is_refused(self):
        self.assertEqual(self._call("/configurator/variant_image", token="faux",
                                    product_id=1, image=png()),
                         {"error": "unknown_session"})

    def test_another_variant_is_refused(self):
        """Le jeton autorise SA variante, aucune autre."""
        session, _state = self._confirm(self.small)
        other = self.env["product.product"].search(
            [("id", "!=", session.product_id.id)], limit=1)
        self.assertEqual(self._call("/configurator/variant_image", token=session.access_token,
                                    product_id=other.id, image=png()),
                         {"error": "not_this_variant"})

    def test_not_a_png_or_too_large_is_refused(self):
        """Ni un faux PNG, ni une image de plus de 1024 px."""
        session, _state = self._confirm(self.small)
        bad = base64.b64encode(b"GIF89a pas une image").decode()
        for image in (bad, "§§pas du base64§§", png(1100, 10)):
            self.assertEqual(
                self._call("/configurator/variant_image", token=session.access_token,
                           product_id=session.product_id.id, image=image),
                {"error": "bad_image"})
        self.assertFalse(session.product_id.editor_image_source)

    def test_never_over_the_editors_picture(self):
        """Une variante qui a l'image de l'ÉDITEUR ne la perd jamais."""
        session, _state = self._confirm(self.small)
        session.product_id.write({"image_variant_1920": png(), "editor_image_source": "editor"})
        self.assertEqual(self._call("/configurator/variant_image", token=session.access_token,
                                    product_id=session.product_id.id, image=png(8, 8)),
                         {"error": "not_wanted"})

    def test_never_over_another_customers_picture(self):
        """⚠️ La variante est PARTAGÉE : le second client d'une même combinaison la TROUVE,
        et ne remplace pas l'image du premier."""
        first, _state = self._confirm(self.small)
        self._call("/configurator/variant_image", token=first.access_token,
                   product_id=first.product_id.id, image=png())
        second, state = self._confirm(self.small)
        self.assertEqual(second.product_id, first.product_id)
        self.assertFalse(second.variant_created)
        self.assertIsNone(state["photo"])
        self.assertEqual(self._call("/configurator/variant_image", token=second.access_token,
                                    product_id=second.product_id.id, image=png(8, 8)),
                         {"error": "not_wanted"})
