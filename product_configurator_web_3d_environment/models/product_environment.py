# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class ProductEnvironment(models.Model):
    _inherit = "product.environment"

    placement_ids = fields.One2many("product.environment.placement", "environment_id", string="Placed products")

    def _editor_can_place(self):
        # ⓘ Ce pont installé, une baie peut recevoir un produit : le « + » s'affiche.
        return True

    def editor_state(self):
        state = super().editor_state()
        state["placements"] = [placement.editor_entry() for placement in self.sudo().placement_ids]
        return state

    def _attribute_raw(self, attribute, millimetres):
        """Une mesure de la baie, dans l'unité de l'ATTRIBUT et sous la forme qu'on y saisirait."""
        unit = (attribute.value_in_mm(1.0) or 1.0) if attribute.converts_to_mm() else 1.0
        return "%g" % round(millimetres / unit, 3)

    def place_product(self, opening_id, product_tmpl_id):
        """POSER un produit dans une baie : la configuration naît avec les mesures de la baie (U-2).

        :returns: ``{"placement": {...}}`` ou ``{"error": code, "message": texte}``
        ⚠️ Le produit doit être de ceux que la baie propose (`bay_products`) : la route est publique,
        et un identifiant tapé à la main ne pose pas n'importe quoi.
        """
        self.ensure_one()
        bay = self._bay(opening_id)
        product = self.env["product.template"].sudo().browse(int(product_tmpl_id or 0)).exists()
        offered = bay and product and product.id in [p["id"] for p in self.bay_products(opening_id)["products"]]
        if not offered:
            return {"error": "not_offered", "message": _("This product cannot be placed in this bay.")}
        session = self.env["product.config.session"]
        if product.config_ok:
            session = session.sudo().create_get_session(product.id, force_create=True)
            session._ensure_access_token()
            width_attr, height_attr = self._common_attributes()
            for attribute, measure in ((width_attr, bay["width"]), (height_attr, bay["height"])):
                if not attribute or not product.attribute_line_ids.filtered(lambda l, a=attribute: l.attribute_id == a):
                    continue
                answer = session.web_set_custom_value(attribute.id, self._attribute_raw(attribute, measure))
                if isinstance(answer, dict) and answer.get("error"):
                    # ⓘ La compatibilité l'a déjà vérifié : une borne CONDITIONNELLE du configurateur
                    # peut encore refuser. La pose a lieu, la question reste à régler par le client.
                    _logger.info("Bay %s of environment %s: %s refused %s (%s)", opening_id, self.id,
                                 product.display_name, attribute.display_name, answer.get("message"))
        Placement = self.env["product.environment.placement"].sudo()
        Placement.search([("environment_id", "=", self.id), ("opening_id", "=", opening_id)]).unlink()
        placement = Placement.create({"environment_id": self.id, "opening_id": opening_id,
                                      "product_tmpl_id": product.id, "session_id": session.id or False})
        return {"placement": placement.editor_entry()}
