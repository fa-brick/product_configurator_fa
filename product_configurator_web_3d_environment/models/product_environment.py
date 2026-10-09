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

    @staticmethod
    def _session_measure(session, attribute):
        """La réponse d'une session à un attribut de mesure, en mm — saisie libre ou valeur offerte, ou ``None``."""
        custom = session.custom_value_ids.filtered(lambda c: c.attribute_id == attribute)[:1]
        raw = custom.value if custom else session.value_ids.filtered(lambda v: v.attribute_id == attribute)[:1].name
        number = attribute.parse_number(raw) if raw else None
        if number is None:
            return None
        return attribute.value_in_mm(number) if attribute.converts_to_mm() else number

    def _placement_offsets(self, placement):
        """L'écart de la configuration à sa baie, en mm, par mesure : ``{"width": -400.0, "height": 0.0}``."""
        bay = self._bay(placement.opening_id)
        session = placement.session_id.sudo()
        offsets = {}
        if not bay or not session:
            return offsets
        for key, attribute in zip(("width", "height"), self._common_attributes()):
            measure = attribute and self._session_measure(session, attribute)
            if measure is not None:
                offsets[key] = round(measure - bay[key], 3)
        return offsets

    def editor_save(self, plan, wall_height=None, wall_thickness=None, start_view=False):
        """Enregistrer le plan — et faire SUIVRE aux produits posés les cotes de leur baie (U-2, D-424).

        ⓘ Comme une formule et sa constante (D-047) : le produit reste lié à sa baie, et l'écart que
        le client y a mis se garde. Il se lit au changement — réponse actuelle moins ANCIENNE cote —,
        si bien qu'aucun décalage n'est stocké qui pourrait diverger de la configuration.
        """
        self.ensure_one()
        before = {placement.id: (placement, self._bay(placement.opening_id), self._placement_offsets(placement))
                  for placement in self.sudo().placement_ids.filtered("session_id")}
        result = super().editor_save(plan, wall_height=wall_height, wall_thickness=wall_thickness,
                                     start_view=start_view)
        if not result.get("ok"):
            return result
        followed, messages = [], []
        attributes = dict(zip(("width", "height"), self._common_attributes()))
        for placement, old_bay, offsets in before.values():
            new_bay = self._bay(placement.opening_id)
            if not old_bay or not new_bay:
                continue
            session = placement.session_id.sudo()
            changed = False
            for key, attribute in attributes.items():
                if not attribute or new_bay[key] == old_bay[key]:
                    continue
                target = new_bay[key] + offsets.get(key, 0.0)
                answer = session.web_set_custom_value(attribute.id, self._attribute_raw(attribute, target))
                if isinstance(answer, dict) and answer.get("error"):
                    # ⓘ La baie est enregistrée quand même : c'est elle qui fait foi, le produit
                    # garde sa réponse et le client est prévenu.
                    messages.append(_("%(product)s cannot follow its bay: %(reason)s",
                                      product=placement.product_tmpl_id.display_name,
                                      reason=answer.get("message") or attribute.display_name))
                else:
                    changed = True
            if changed:
                followed.append(session.access_token)
        result.update(followed=followed, messages=messages)
        return result

    def remove_product(self, opening_id):
        """RETIRER le produit posé dans une baie — le menu flottant (étape 8.4f).

        ⓘ La configuration n'est pas supprimée : elle reste une session en cours, comme une
        configuration abandonnée sur le site ; seul le lien à la baie disparaît.
        """
        self.ensure_one()
        placement = self.sudo().placement_ids.filtered(lambda p: p.opening_id == opening_id)
        if not placement:
            return {"error": "not_placed"}
        placement.unlink()
        return {"ok": True}

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
