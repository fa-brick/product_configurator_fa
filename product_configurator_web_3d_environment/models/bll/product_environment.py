"""Ce qu'exécute `product.environment` (BLL, D-541).

L'AFFICHAGE des listes de matières d'un environnement — celui d'un attribut (W-113, E-3c-3, D-451).

Chaque usage (mur extérieur, mur intérieur, sol) se montre dans la barre de droite comme une question de la page du
configurateur : même forme, même marque, même taille, même disposition, et rien de plus (§21.5).
"""
import logging
from odoo import _, models

_logger = logging.getLogger(__name__)


#: Ce que l'onglet Infos règle sur un usage : ses clés JS, et le champ de chacune.
DISPLAY_FIELDS = {"displayType": "display_type", "swatchMark": "swatch_mark", "answerSize": "answer_size",
                  "answerLayout": "answer_layout"}


class ProductEnvironment(models.Model):
    _inherit = "product.environment"

    def _montage(self):
        """Les placements du MONTAGE courant de ce chantier.

        ⓘ Ici, tous ceux de l'environnement ; le pont de vente le restreint au devis en cours
        (E-1 : le montage est lié au devis), si bien qu'un même chantier porte un montage par devis.
        """
        return self.sudo().placement_ids

    def _placement_values(self, opening_id, product, session):
        """Les valeurs d'un placement neuf — ⓘ le pont de vente y ajoute son devis."""
        return {"environment_id": self.id, "opening_id": opening_id,
                "product_tmpl_id": product.id, "session_id": session.id or False}

    def _editor_can_place(self):
        # ⓘ Ce pont installé, une baie peut recevoir un produit : le « + » s'affiche.
        return True

    def editor_state(self):
        state = super().editor_state()
        state["placements"] = [placement.editor_entry() for placement in self._montage()]
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
        for key in ("width", "height"):
            # ⓘ L'attribut qui tient cette cote SUR CE PRODUIT : le rôle de son modèle, sinon l'attribut commun (lot 1).
            attribute = placement.product_tmpl_id._dimension_attribute(key)
            # ⚠️ Pas `attribute and …` : un attribut non réglé est un recordset VIDE, que `and` rendrait au lieu de
            # `None` — et la soustraction tombait à la première pose (L-561).
            measure = self._session_measure(session, attribute) if attribute else None
            if measure is not None:
                offsets[key] = round(measure - bay[key], 3)
        return offsets

    def _lost_placements(self, plan):
        """Les placements du montage dont ce plan RETIRE la baie.

        ⚠️ Sans ce refus, une baie recréée sous le même identifiant (`o1` d'une autre forme) reprenait le
        produit de l'ancienne, sans contrôle ni message (§14.5).
        """
        # ⓘ Tout trou reçoit un produit : il n'y a plus de rôle « baie » (D-452).
        bays = {opening.get("id") for opening in (plan or {}).get("openings") or [] if isinstance(opening, dict)}
        return self._montage().filtered(lambda placement: placement.opening_id not in bays)

    def editor_save(self, plan, wall_height=None, wall_thickness=None, start_view=False, template_id=None):
        """Enregistrer le plan — et faire SUIVRE aux produits posés les cotes de leur baie (U-2, D-424).

        ⓘ Comme une formule et sa constante (D-047) : le produit reste lié à sa baie, et l'écart que
        le client y a mis se garde. Il se lit au changement — réponse actuelle moins ANCIENNE cote —,
        si bien qu'aucun décalage n'est stocké qui pourrait diverger de la configuration.
        """
        self.ensure_one()
        lost = self._lost_placements(plan)
        if lost:
            return {"error": "invalid", "messages": [
                _("%(product)s is placed in a bay that this plan removes: remove the product first.",
                  product=placement.product_tmpl_id.display_name) for placement in lost]}
        # ⚠️ Pas le trou qui SUIT son produit (E-3d-5b) : le produit y suivrait le trou qui le suit — chacun écrirait
        # l'autre à chaque enregistrement.
        before = {placement.id: (placement, self._bay(placement.opening_id), self._placement_offsets(placement))
                  for placement in self._montage().filtered("session_id")
                  if (self._bay(placement.opening_id) or {}).get("follows") != "product"}
        result = super().editor_save(plan, wall_height=wall_height, wall_thickness=wall_thickness,
                                     start_view=start_view, template_id=template_id)
        if not result.get("ok"):
            return result
        followed, messages = [], []
        for placement, old_bay, offsets in before.values():
            new_bay = self._bay(placement.opening_id)
            if not old_bay or not new_bay:
                continue
            session = placement.session_id.sudo()
            changed = False
            # ⓘ Le rôle « dimensions » du produit posé, sinon l'attribut commun (lot 1).
            attributes = {key: placement.product_tmpl_id._dimension_attribute(key) for key in ("width", "height")}
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
        placement = self._montage().filtered(lambda p: p.opening_id == opening_id)
        if not placement:
            return {"error": "not_placed"}
        placement.unlink()
        return {"ok": True}

    @staticmethod
    def _select_shape_value(session, product, opening_type_id):
        """Répondre à la *Forme* du produit par la valeur du type de trou — rien s'il n'en a pas.

        ⓘ La règle de `/configurator/set_value` pour une question à choix unique : la valeur remplace celle de son
        attribut.
        """
        value = product._environment_shape_value(opening_type_id) if opening_type_id else None
        if not value:
            return
        others = session.value_ids.filtered(lambda v, a=value.attribute_id: v.attribute_id != a)
        session.write({"value_ids": [(6, 0, (others | value).ids)]})

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
        # ⓘ Un trou qui SUIT son produit (le neuf, E-3d-5b) ne lui impose rien : le produit naît à ses réponses par
        # défaut, et c'est le trou qui prendra son perçage.
        follows = bay.get("follows") == "product"
        if product.config_ok:
            session = session.sudo().create_get_session(product.id, force_create=True)
            session._ensure_access_token()
        if product.config_ok and not follows:
            # ⓘ La FORME d'abord (E-3d-4b, Q-30.4) : la valeur du type du trou — une fenêtre cintrée dans un trou cintré ;
            # les bornes des cotes peuvent en dépendre.
            self._select_shape_value(session, product, bay.get("type"))
            # ⓘ Le rôle « dimensions » du produit, sinon l'attribut commun : le même que celui du filtre (lot 1).
            width_attr, height_attr = product._dimension_attribute("width"), product._dimension_attribute("height")
            for attribute, measure in ((width_attr, bay["width"]), (height_attr, bay["height"])):
                if not attribute or not product.attribute_line_ids.filtered(lambda l, a=attribute: l.attribute_id == a):
                    continue
                answer = session.web_set_custom_value(attribute.id, self._attribute_raw(attribute, measure))
                if isinstance(answer, dict) and answer.get("error"):
                    # ⓘ La compatibilité l'a déjà vérifié : une borne CONDITIONNELLE du configurateur
                    # peut encore refuser. La pose a lieu, la question reste à régler par le client.
                    _logger.info("Bay %s of environment %s: %s refused %s (%s)", opening_id, self.id,
                                 product.display_name, attribute.display_name, answer.get("message"))
        # ⓘ Une baie, un produit — dans le montage COURANT : un autre devis du même chantier garde le sien.
        self._montage().filtered(lambda p: p.opening_id == opening_id).unlink()
        placement = self.env["product.environment.placement"].sudo().create(
            self._placement_values(opening_id, product, session))
        return {"placement": placement.editor_entry()}

    def _material_use_values(self, values):
        vals = super()._material_use_values(values)
        if vals is None:
            return None
        Use = self.env["product.environment.material.use"]
        for key, name in DISPLAY_FIELDS.items():
            if key not in values:
                continue
            allowed = {value for value, _label in Use._fields[name]._description_selection(self.env)}
            if values[key] not in allowed:
                return None
            vals[name] = values[key]
        return vals


class ProductEnvironmentMaterialDisplay(models.Model):
    _inherit = "product.environment"

    def editor_state(self):
        state = super().editor_state()
        # ⓘ Les choix de l'onglet Infos, traduits — au back-office seulement, comme les catégories (Q-24.2).
        if state.get("can_set_material_uses"):
            Use = self.env["product.environment.material.use"]
            state["materialDisplayOptions"] = {
                key: [[value, label] for value, label in Use._fields[name]._description_selection(self.env)]
                for key, name in DISPLAY_FIELDS.items()
            }
        return state
