# -*- coding: utf-8 -*-
"""L'image d'une variante née d'une configuration — D-399, lot 5 (voie A).

Gerry, 2026-10-05 : *« A pour l'ajout au panier puis B quand c'est possible »*, puis *« pour
tout devis / commande dont le variant n'est pas créé »*. Quand une confirmation sur la page 3D
CRÉE la variante, le navigateur du client la photographie — sous la vue de l'appareil photo,
avec le décor, les surfaces d'ombre et le cadre commun de la pièce — et l'image part ici.
L'éditeur la remplacera par la sienne (voie B : `editor_image_source = 'client'`, compteur,
activité, avis).

⚠️ **LA VARIANTE EST PARTAGÉE** : tout client qui choisit la même combinaison reçoit le même
`product.product` (`search_variant`). On n'écrit donc que sur une variante que CETTE session
a créée, ou qui n'a encore aucune image — jamais par-dessus celle d'un autre client, ni
jamais par-dessus celle de l'éditeur.

Plan : `product_3Dmodel/_bmad-output/implementation-artifacts/plan-images-des-variantes.md` §5.
"""
import base64
import binascii
import io
import json
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

# Une image de 1024 px en PNG pèse quelques centaines de kilo-octets ; au-delà, ce n'est pas
# une photo de la page.
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_IMAGE_SIDE = 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    variant_created = fields.Boolean(
        string="Variant created by this configuration", readonly=True, copy=False,
        help="The confirmation of this configuration CREATED its variant — it did not find "
             "an existing one. Only such a variant receives the picture taken by the "
             "customer's browser.",
    )

    def create_get_variant(self, value_ids=None, custom_vals=None):
        """Retenir si la variante est NÉE de cette confirmation.

        ⓘ `create_get_variant` rend la même chose qu'il ait trouvé ou créé : on compare donc
        les variantes de l'article avant et après — archivées comprises, une variante
        réactivée n'étant pas une variante neuve.
        """
        before = set(self.product_tmpl_id.with_context(active_test=False)
                     .product_variant_ids.ids)
        variant = super().create_get_variant(value_ids=value_ids, custom_vals=custom_vals)
        for session in self:
            session.variant_created = bool(variant) and variant.id not in before
        return variant

    # ------------------------------------------------------------------
    # Ce que la page doit photographier
    # ------------------------------------------------------------------

    def _web_photo_wanted(self):
        """La page doit-elle photographier la variante qu'elle vient de confirmer ?"""
        self.ensure_one()
        variant = self.product_id
        if self.state != "done" or not variant:
            return False
        if variant.editor_image_source == "editor":
            return False
        root = self._web_model3d()
        if not root or not root.preview_managed:
            return False
        return bool(self.variant_created or not variant.image_variant_1920)

    def _web_photo(self):
        """La prise de vue que la page rejoue : la vue de l'appareil photo, sa projection, le
        décor de la pièce, ses surfaces d'ombre et le cadre de ses variantes."""
        self.ensure_one()
        if not self._web_photo_wanted():
            return None
        root = self._web_model3d()
        camera = self.env["product.model3d.camera"].sudo().search(
            [("model3d_id", "=", root.id), ("is_thumbnail", "=", True)], limit=1)
        view = self._web_camera_view(camera)
        if not view:
            return None
        framing = None
        if root.variant_image_framing == "pose":
            framing = {"mode": "pose"}
        elif root.variant_image_framing == "common" and camera.variant_frame_radius:
            try:
                stored = json.loads(camera.variant_frame_center or "null")
            except ValueError:
                stored = None
            centre = stored.get("centre") if isinstance(stored, dict) else stored
            if isinstance(centre, list) and len(centre) == 3:
                framing = {
                    "mode": "fixed",
                    "centre": {"x": centre[0], "y": centre[1], "z": centre[2]},
                    "radius": camera.variant_frame_radius,
                    "halfHeight": stored.get("halfHeight") if isinstance(stored, dict) else None,
                }
        return {
            "pose": view["pose"],
            "target": view["target"],
            "projection": view["projection"],
            "fov": view["fov"],
            "backdrop": root.preview_backdrop_effective,
            "bgColor": root.preview_bg_color_effective,
            "surfaces": {
                "floor": camera.shadow_floor,
                "backWall": camera.shadow_back_wall,
                "sideWall": camera.shadow_side_wall,
            },
            "framing": framing,
            "size": MAX_IMAGE_SIDE,
        }

    def web_state(self):
        """L'état de la page, plus la prise de vue à rejouer quand la variante en attend une."""
        state = super().web_state()
        state["photo"] = self._web_photo()
        return state

    # ------------------------------------------------------------------
    # L'image envoyée par la page
    # ------------------------------------------------------------------

    def web_store_variant_image(self, product_id, image_b64):
        """Écrire l'image de la variante — sous toutes les gardes, ou pas du tout.

        :return: `{"ok": True}` ou `{"error": <raison>}`
        """
        self.ensure_one()
        variant = self.product_id
        if self.state != "done" or not variant or variant.id != int(product_id or 0):
            return {"error": "not_this_variant"}
        if not self._web_photo_wanted():
            return {"error": "not_wanted"}
        raw = self._web_checked_png(image_b64)
        if raw is None:
            return {"error": "bad_image"}
        variant.sudo().write({
            "image_variant_1920": base64.b64encode(raw),
            "editor_image_source": "client",
        })
        return {"ok": True}

    @staticmethod
    def _web_checked_png(image_b64):
        """Les octets d'un PNG de 1024 px au plus, ou `None`.

        ⚠️ La route est PUBLIQUE : on ne fait confiance ni au type ni à la taille annoncés.
        On décode, on lit la signature, on ouvre l'image, on mesure.
        """
        if not image_b64 or not isinstance(image_b64, str):
            return None
        if len(image_b64) > MAX_IMAGE_BYTES * 4 // 3 + 16:
            return None
        try:
            raw = base64.b64decode(image_b64, validate=True)
        except (binascii.Error, ValueError):
            return None
        if len(raw) > MAX_IMAGE_BYTES or not raw.startswith(PNG_SIGNATURE):
            return None
        try:
            from PIL import Image
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                width, height = image.size
        except Exception:  # noqa: BLE001 — toute image illisible est refusée de même
            _logger.info("Image de variante refusée : PNG illisible.")
            return None
        if width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE:
            return None
        return raw
