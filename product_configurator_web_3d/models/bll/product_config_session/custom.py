"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def _web_root_custom(self):
        """`{attribut → saisie rangée}` — ce que le client a TAPÉ à la racine."""
        self.ensure_one()
        return {
            record.attribute_id.id: record.value
            for record in self.custom_value_ids
            if record.value not in (None, False, "")
        }

    def _web_child_custom(self, link_id):
        """`{attribut → saisie rangée}` d'un placement — clés entières ([[L-219]])."""
        self.ensure_one()
        raw = (self.child_custom_values or {}).get(str(int(link_id))) or {}
        out = {}
        for attr_key, text in raw.items():
            try:
                out[int(attr_key)] = text
            except (TypeError, ValueError):
                continue
        return out

    @api.model
    def _web_parsed_custom(self, typed):
        """`{attribut → nombre ou texte}` — la forme qu'attendent bornes et conditions."""
        out = {}
        for attr_id, text in (typed or {}).items():
            attribute = self.env["product.attribute"].browse(attr_id).exists()
            if not attribute:
                continue
            number = attribute.parse_number(text) if attribute.is_numeric() else None
            out[attr_id] = number if number is not None else text
        return out

    def web_set_custom_value(self, attribute_id, raw, link_id=None):
        """Répondre à une question par SAISIE — à la racine ou pour un placement (D-353).

        Dans l'ordre, et chaque étape pour sa raison :

        1. **la question accepte-t-elle une saisie ?** — sur la LIGNE (et, pour un
           placement, seulement si la définition la dit éditable, comme D-332) ;
        2. **la saisie désigne-t-elle une valeur DÉJÀ OFFERTE ?** Alors c'est un CHOIX,
           rangé comme un clic : rien de neuf n'attend la confirmation ;
        3. **est-elle valide ?** — bornes et pas d'un nombre, longueur et format d'un
           texte, **au serveur** : la route est publique ;
        4. **la ranger dans la session**, jamais au catalogue. La valeur d'attribut naît à
           la CONFIRMATION (D-353), réutilisée si elle existe déjà.

        Une saisie VIDE efface la réponse tapée.

        :returns: l'état complet, ou `{"error": code, "message": texte}` — le message est
            déjà traduit, et c'est lui que la page affiche.
        """
        self.ensure_one()
        attribute = self.env["product.attribute"].browse(int(attribute_id or 0)).exists()
        if not attribute:
            return {"error": "unknown_value"}
        raw = self._web_strip_unit(attribute, raw)
        if link_id:
            return self._web_set_child_custom(int(link_id), attribute, raw)
        line = self.product_tmpl_id.attribute_line_ids.filtered(
            lambda l: l.attribute_id == attribute
        )[:1]
        if not line or not self._web_free_field(line):
            return {"error": "custom_not_allowed"}
        text = attribute.canonical_custom_answer(raw)
        offered = line.offered_value_for(raw) if text is not None else None
        try:
            if offered:
                self.update_config({attribute.id: offered.id}, {attribute.id: False})
            elif text is None:
                self.update_config({}, {attribute.id: False})
            else:
                custom_vals = dict(self._get_custom_vals_dict())
                custom_vals.update(self._web_parsed_custom({attribute.id: text}))
                line.validate_custom_val(
                    text, value_ids=self.value_ids.ids, custom_vals=custom_vals
                )
                self.update_config({attribute.id: False}, {attribute.id: text})
        except ValidationError as exc:
            return {"error": "invalid_custom", "message": str(exc.args[0] if exc.args else exc)}
        # ⓘ La trace de D-253 ne regarde que les valeurs CHOISIES : une saisie seule ne
        # préviendrait personne. Même geste que `web_set_child_value`.
        self._notify_configuration_changed()
        return self.web_state()

    @api.model
    def _web_strip_unit(self, attribute, raw):
        """« 180 mm » → « 180 » : l'unité que le client a tapée par habitude.

        ⓘ Le champ l'affiche à côté de lui, et la liste de suggestions la porte : il
        est naturel de la retaper. La refuser ferait dire « pas un nombre » à une
        largeur parfaitement claire.
        """
        # ⓘ Des plages aussi : « 3-34, 45 cm » se retape avec son unité, comme une largeur (D-533).
        if raw in (None, False) or not (attribute.is_numeric() or attribute.is_ranges()) \
                or not attribute.uom_id:
            return raw
        text = str(raw).strip()
        unit = attribute.uom_id.name or ""
        if unit and text.lower().endswith(unit.lower()):
            text = text[: -len(unit)].strip()
        return text

    def _web_set_child_custom(self, link_id, attribute, raw):
        """La saisie d'un PLACEMENT — mêmes étapes, rangée par lien (D-332, D-353)."""
        model3d = self._web_model3d()
        values = self._web_values()
        definition = (model3d.to_definition(values, link_answers=self._web_link_answers())
                      if model3d else None)
        placements = self._web_placements(model3d, definition, values)
        placement = next((p for p in placements.values()
                          if p.get("linkId") == link_id), None)
        question = next((q for q in (placement or {}).get("questions", [])
                         if q["id"] == attribute.id), None)
        if not question:
            return {"error": "unknown_value"}
        if not question.get("free"):
            return {"error": "custom_not_allowed"}
        model_id = self._web_placement_model_id(definition, placement["nodeId"])
        tmpl = self.env["product.model3d"].sudo().browse(model_id).product_tmpl_id
        line = tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id == attribute)[:1]
        key = str(link_id)
        answers = dict((self.child_values or {}).get(key) or {})
        typed = dict((self.child_custom_values or {}).get(key) or {})
        text = attribute.canonical_custom_answer(raw)
        offered = line.offered_value_for(raw) if text is not None else None
        attr_key = str(attribute.id)
        if offered:
            answers[attr_key] = offered.id
            typed.pop(attr_key, None)
        elif text is None:
            typed.pop(attr_key, None)
        else:
            chosen = [v["id"] for q in placement["questions"] for v in q["values"]
                      if v["chosen"] and q["id"] != attribute.id]
            parsed = self._web_parsed_custom(self._web_child_custom(link_id))
            parsed.update(self._web_parsed_custom({attribute.id: text}))
            try:
                line.validate_custom_val(text, value_ids=chosen, custom_vals=parsed)
            except ValidationError as exc:
                return {"error": "invalid_custom",
                        "message": str(exc.args[0] if exc.args else exc)}
            answers.pop(attr_key, None)
            typed[attr_key] = text
        child_values = dict(self.child_values or {})
        child_values[key] = answers
        child_custom = dict(self.child_custom_values or {})
        child_custom[key] = typed
        self.write({"child_values": child_values, "child_custom_values": child_custom})
        self._notify_configuration_changed()
        return self.web_state()
