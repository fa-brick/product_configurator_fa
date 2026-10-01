# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""L'état d'une session, tel que la PAGE PUBLIQUE le lit — D-091, lot 6.

Ce module ne sait rien du HTTP : il rend un dictionnaire. Le contrôleur ne fait
que l'appeler, ce qui rend l'essentiel éprouvable **sans serveur** — et c'est ce
qui manquait au lot 6, dont le blocage n° 4 était l'absence de tout harnais.

⚠️ **Ce que la page reçoit, et ce qu'elle ne reçoit PAS.** Elle reçoit les
questions, leurs réponses possibles, le prix et la définition 3D. Elle ne reçoit
ni identifiant interne de session, ni jeton d'une autre, ni rien qui permette
d'énumérer : le jeton entre, il ne ressort pas.
"""
import logging
from collections import Counter

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    # ── LES RÉPONSES PAR PLACEMENT — D-332 ──────────────────────────────────
    #
    # `value_ids` porte les réponses de la RACINE. Un enfant posé par un lien a ses propres
    # questions ; celles que l'auteur n'a pas fixées sur le lien se répondent ICI, par lien :
    # `{"<id de lien>": {"<id d'attribut>": <id de valeur>}}`. ⚠️ Les clés d'un `Json` sont
    # des CHAÎNES ([[L-219]]) : tout lecteur les convertit, jamais ne les compare brutes.
    #
    # ⓘ Une OCCURRENCE de répétition partage les réponses de son lien source — répondre
    # par copie est le cas de D-175, plus tard.
    child_values = fields.Json(
        string="Answers per placement", default=lambda self: {},
        help="Answers of the client to the questions of a placed part, per link.",
    )
    # La VARIANTE de chaque placement répondu, née à la confirmation — `{"<lien>": id}`.
    # ⚠️ Sans effet commercial tant que 7-9/7-10 ne sont pas faites : retenue, pas commandée.
    child_variants = fields.Json(
        string="Variants per placement", default=lambda self: {},
        help="Variant derived at confirmation for each answered placement.",
    )
    # Les SAISIES LIBRES par placement — `{"<lien>": {"<attribut>": "<saisie rangée>"}}`
    # (D-353). ⚠️ **Un champ À PART, pas dans `child_values`** : tous les lecteurs de
    # celui-ci attendent un IDENTIFIANT de valeur (`int(value_id)`), et une chaîne y
    # glissée les ferait tomber — ou pire, lire « 1500 » comme la valeur n° 1500.
    child_custom_values = fields.Json(
        string="Typed answers per placement", default=lambda self: {},
        help="Free answers typed by the client for a placed part, per link. They "
             "become attribute values only when the configuration is confirmed.",
    )

    def _web_step_layout(self):
        """Les ÉTAPES que la page montre, et l'étape de chaque question — D-385.

        ⚠️ **L'ÉTAPE EST UN MARQUEUR, PAS UN CONTENANT** (D-202) : la ligne qui
        porte `config_step_id` l'ouvre, et les lignes suivantes lui appartiennent
        jusqu'au marqueur d'après. On relit donc les lignes DANS L'ORDRE, comme
        `config_step_owner_id`, plutôt que `step_line.attribute_line_ids`, qui ne
        dit rien des lignes placées avant la première étape.

        ⚠️ **UNE ÉTAPE MASQUÉE PAR SA CONDITION EMPORTE SES QUESTIONS** (D-086) :
        elles ne s'affichent pas et ne sont pas exigées. C'est ce que le
        back-office fait déjà (`validate_configuration` ne contrôle que les
        étapes ouvertes).

        ⓘ **Les lignes AVANT la première étape rejoignent la première étape
        visible** — arbitré par Gerry le 2026-09-30. Sans étape visible, elles
        restent hors étape, et la page les montre à plat comme avant.

        :returns: ``(steps, step_of, hidden)`` — les étapes visibles
            ``[{"id", "name", "lines"}]`` dans l'ordre, l'étape de chaque ligne
            ``{line_id: step_line_id | None}``, et les lignes d'une étape masquée.
        """
        self.ensure_one()
        tmpl = self.product_tmpl_id
        chosen = self.value_ids.ids
        custom_vals = self._get_custom_vals_dict()
        step_lines = {sl.config_step_id: sl for sl in tmpl.config_step_line_ids}
        steps, leading = [], []
        hidden = self.env["product.template.attribute.line"]
        current, opened = None, False
        for line in tmpl.attribute_line_ids.sorted():
            step_line = step_lines.get(line.config_step_id)
            if step_line:
                opened = True
                current = None
                if step_line._is_visible(chosen, custom_vals):
                    current = {"id": step_line.id, "name": step_line.name, "lines": []}
                    steps.append(current)
            if current:
                current["lines"].append(line)
            elif opened:
                hidden |= line
            else:
                leading.append(line)
        if steps:
            steps[0]["lines"][:0] = leading
        step_of = {line.id: step["id"] for step in steps for line in step["lines"]}
        for line in leading:
            step_of.setdefault(line.id, None)
        return steps, step_of, hidden

    def _web_views(self, steps, model3d):
        """Les VUES 3D des étapes et des questions — D-385, D-387.

        ⓘ Une vue est celle qu'on a posée, sinon RIEN : la caméra ne bouge pas —
        l'arbitrage de `_resolve_view_camera`. La page résout ensuite « l'attribut,
        sinon son étape » (D-163) au moment où l'on ouvre ou répond à une question.

        ⚠️ La définition n'est calculée qu'UNE fois, et seulement si une vue vise une
        pièce : c'est l'objet le plus cher de la réponse.

        :returns: ``(par_etape, par_question)`` — ``{step_line_id: vue}`` et
            ``{attribute_id: vue}``, sans les entrées vides.
        """
        step_lines = self.env["product.config.step.line"].sudo()
        by_step = {step["id"]: step_lines.browse(step["id"]).view_camera_id for step in steps}
        by_question = {
            line.attribute_id.id: line.view_camera_id
            for line in self.product_tmpl_id.attribute_line_ids
            if line.view_camera_id
        }
        cameras = [camera for camera in (*by_step.values(), *by_question.values()) if camera]
        definition = None
        if model3d and any(camera.target_kind == "piece" for camera in cameras):
            definition = model3d.to_definition()

        def views(table):
            return {key: self._web_camera_view(camera, definition)
                    for key, camera in table.items() if camera}

        return views(by_step), views(by_question)

    def _web_steps(self, steps, step_views):
        """Les étapes telles que la page les reçoit — avec la VUE de chacune (D-385)."""
        return [
            {"id": step["id"], "name": step["name"], "camera": step_views.get(step["id"])}
            for step in steps
        ]

    def _web_attribute_lines(self, layout=None):
        """Les questions du produit, avec ce qui reste disponible.

        ⚠️ La disponibilité se demande à `values_available` — celle qui sert déjà
        à l'assistant — et non à une règle réécrite ici. Deux évaluateurs d'une
        même restriction finiraient par diverger, et c'est le client qui verrait
        la différence.

        ⓘ Chaque question porte son ÉTAPE (`stepId`) et dit si elle MANQUE
        (`missing`) : c'est ce qui grise les pastilles d'étape de la page (D-385).
        Le même évaluateur que la confirmation (`_web_missing_attributes`), pour
        que la page ne grise jamais ce que le serveur accepterait.
        """
        self.ensure_one()
        chosen = self.value_ids.ids
        typed = self._web_root_custom()
        custom_vals = self._get_custom_vals_dict()
        layout = layout or self._web_step_layout()
        _steps, step_of, hidden = layout
        missing = self._web_missing_attributes(layout=layout)
        out = []
        for line in self.product_tmpl_id.attribute_line_ids.sorted():
            if line in hidden:
                continue
            values = self._web_offered_values(line)
            available = set(
                self.values_available(
                    check_val_ids=values.ids,
                    value_ids=chosen,
                    custom_vals=custom_vals,
                    product_template_attribute_line_id=line.id,
                )
            )
            values = self._web_shown_values(line, values, available, chosen)
            categories, category_keys = self._web_categorized(values)
            out.append({
                "id": line.attribute_id.id,
                "name": line.attribute_id.name,
                "required": bool(line.required),
                "multi": bool(line.multi),
                # ⓘ D-385 — l'étape (`step.line`) qui porte la question, `None` hors
                # étape ; et si une réponse obligatoire y manque encore.
                "stepId": step_of.get(line.id),
                "missing": line in missing,
                # ⓘ **LA SAISIE LIBRE** (D-353) — la forme du champ, ou `None` quand la
                # question se répond par sa liste ; et ce que le client a déjà tapé.
                "free": self._web_free_field(line),
                "customValue": typed.get(line.attribute_id.id),
                # ⚠️ **LA FORME QU'ON A DONNÉE À LA QUESTION.** Réglée en
                # back-office depuis toujours, elle n'était pas servie : la page
                # rendait un bouton pour tout, quel que soit le type. Cinq
                # formes chez Odoo, plus la « carte » — une vignette et son
                # libellé — qui manquait pour une valeur désignant un produit.
                "displayType": line.attribute_id.display_type,
                # ⓘ La marque du choix d'une grande pastille : coche ou anneau.
                "swatchMark": line.attribute_id.swatch_mark,
                # ⓘ La taille d'une carte ou d'une grande pastille (D-382).
                "answerSize": line.attribute_id.answer_size,
                # ⓘ Sa disposition, déjà ramenée à ce que la forme permet (D-382).
                "answerLayout": line.attribute_id._web_answer_layout(),
                # ⓘ Les catégories de SES réponses — les pastilles du panneau (D-382).
                "categories": categories,
                "values": [
                    {
                        "id": value.id,
                        # ⓘ **La forme AFFICHÉE, pas la forme rangée** — D-160.
                        # Sur une question numérique, la valeur en base est le
                        # nombre nu ; le client, lui, lit « 2400 mm ». Sans cette
                        # ligne le back-office portait l'unité et la page non,
                        # pour la même largeur (demande de Gerry, 2026-09-07).
                        # Sur toute autre question, le formateur rend le libellé
                        # inchangé — il n'y a rien à ajouter à « Chêne ».
                        "name": value.display_value or value.name,
                        # ⓘ La forme RANGÉE (« 150 »), que le champ de saisie
                        # affiche quand la valeur est choisie (D-353).
                        "raw": value.name,
                        # ⚠️ La valeur INDISPONIBLE est rendue quand même, marquée —
                        # sauf si sa question la MASQUE (`_web_shown_values`, D-168).
                        # Grisée, un appui dira pourquoi (D-178).
                        "available": value.id in available,
                        "chosen": value.id in chosen,
                        # ⓘ Les catégories de la réponse, par clé (D-382).
                        "categoryKeys": category_keys[value.id],
                        # La PASTILLE d'une valeur de couleur — telle qu'Odoo la
                        # range, sans interprétation.
                        "color": value.html_color or None,
                        # ⓘ Une URL, jamais des octets : elle passe par le cache du
                        # navigateur, là où un base64 repartirait à chaque réponse.
                        # `_web_value_image` dit si l'image EXISTE — une vignette
                        # promise et vide est pire qu'une absence.
                        "image": (
                            "/configurator/value/%s/image" % value.id
                            if self._web_value_has_image(value) else None
                        ),
                    }
                    for value in values
                ],
            })
        return out

    # ── LES CATÉGORIES DES RÉPONSES — D-382 ────────────────────────────────

    @api.model
    def _web_categorized(self, values):
        """Les catégories d'une question, et celles de chacune de ses réponses — D-382.

        Rend `(categories, keys)` : la liste `[{key, name}]` des catégories PRÉSENTES parmi
        les réponses montrées, dans l'ordre d'affichage (séquence, puis nom), et, par réponse,
        la liste de ses clés. Les catégories viennent de `_web_categories()` de la valeur :
        la MATIÈRE ici, le PRODUIT par la boutique (`product_configurator_web_sale`).

        ⓘ **Seule la FEUILLE se nomme** (Gerry, 2026-09-30) — sauf quand deux feuilles
        portent le même nom : le parent vient alors entre parenthèses, et seulement là.
        """
        seen, keys = {}, {}
        for value in values:
            found = value._web_categories()
            keys[value.id] = [category["key"] for category in found]
            for category in found:
                seen.setdefault(category["key"], category)
        ordered = sorted(seen.values(), key=lambda c: (c["sequence"], c["name"].lower()))
        homonyms = Counter(category["name"] for category in ordered)
        categories = [{
            "key": category["key"],
            "name": ("%s (%s)" % (category["name"], category["parent"])
                     if homonyms[category["name"]] > 1 and category["parent"]
                     else category["name"]),
        } for category in ordered]
        return categories, keys

    # ── LA SAISIE LIBRE — D-353 ─────────────────────────────────────────────

    @api.model
    def _web_free_field(self, line):
        """La forme du CHAMP DE SAISIE d'une question — ou `None` si elle se répond par sa liste.

        ⚠️ **Le discriminant est l'AJOUT, lu sur la LIGNE**, jamais une nouvelle forme
        d'affichage : une forme inconnue disparaît sans erreur des pages d'Odoo, et le
        lot C qui en ajoutait une a été abandonné pour cette raison (2026-09-08).

        ⓘ Trois exclusions, chacune pour sa raison : une question MULTIPLE garde ses cases
        (hors v1, D-353 arbitrage 5) ; une réponse qui désigne un PRODUIT ou une MATIÈRE ne
        se tape pas au clavier ; une question sans ajout n'a que sa liste.

        La forme vient d'`answer_field` (D-244) — ce que l'éditeur lit déjà. La redire
        ici ferait deux descriptions d'un même champ, libres de diverger ([[L-034]]).
        """
        attribute = line.attribute_id
        if not line.custom or line.multi or attribute.value_type != "value":
            return None
        spec = line.answer_field or {}
        numeric = bool(spec.get("numeric"))
        return {
            "numeric": numeric,
            "unit": spec.get("unit_label") or "",
            # ⓘ `None` pour « pas de borne » : une borne à zéro est une vraie borne.
            "min": spec.get("min_val") if numeric and spec.get("has_min_val") else None,
            "max": spec.get("max_val") if numeric and spec.get("has_max_val") else None,
            "step": (spec.get("step") or None) if numeric else None,
            "maxLength": spec.get("max_length") or None,
            "regexp": spec.get("regexp") or None,
        }

    def _web_offered_values(self, line):
        """Les valeurs qu'une question OFFRE — sans la valeur « Custom » d'OCA.

        ⚠️ `_configurator_value_ids()` ajoute cette valeur spéciale à toute ligne qui
        autorise l'ajout : c'est le jeton par lequel l'ancien assistant ouvrait son champ.
        Elle appartient à un AUTRE attribut, et la page la rendait comme une réponse —
        un bouton « Custom » sur chaque question de la Caisse, qu'on ne pouvait que
        refuser (relevé le 2026-09-25). Ici, la saisie a son propre champ.
        """
        return line._configurator_value_ids() - self.get_custom_value_id()

    @api.model
    def _web_shown_values(self, line, values, available, chosen):
        """Les valeurs que la page MONTRE : toutes, ou seulement les disponibles — D-168.

        ⓘ Filtré ICI plutôt que dans la page : une seule règle, rien d'envoyé pour
        rien (un nuancier de 213 teintes), et les formes sans marque de grisé — la
        liste déroulante, les suggestions de saisie — en profitent sans changer.

        ⚠️ **Une valeur CHOISIE reste montrée**, même indisponible. À la racine, cela
        n'arrive pas (`write` de la session retire ce qui ne l'est plus) ; sur une
        pièce posée, si : la réponse du placement n'est pas élaguée. La cacher ferait
        une question répondue sans réponse visible.
        """
        if line._unavailable_display() != "hide":
            return values
        chosen = set(chosen)
        return values.filtered(lambda v: v.id in available or v.id in chosen)

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
           la CONFIRMATION (Gerry, 2026-09-25), réutilisée si elle existe déjà.

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
        if raw in (None, False) or not attribute.is_numeric() or not attribute.uom_id:
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

    @api.model
    def _web_value_has_image(self, value):
        """La chaîne des provenances appartient à la VALEUR, pas à la page.

        ⚠️ Elle a vécu ici, et c'était une erreur de rangement : le back-office
        et la page du client auraient fini par montrer deux vignettes différentes
        pour la même valeur. `_preview_source()` est déclarée dans le module
        attribut et complétée par le pont 3D — D-258.

        ⓘ En `sudo` : un visiteur ne lit ni un composant non publié, ni le
        catalogue des matières. Seule l'existence de l'image est révélée ici ;
        l'image elle-même sort par la route, qui est aussi en `sudo`.
        """
        record, _field = value.sudo()._preview_source()
        return bool(record)

    def _web_model3d(self):
        """Le modèle 3D du produit configuré, ou rien."""
        self.ensure_one()
        # ⚠️ `_root_model3d` vient de l'ÉDITEUR (LGPL) ; ce module dépend des deux,
        # et c'est le seul endroit du dépôt qui en ait le droit (D-075).
        return self.product_tmpl_id._root_model3d()

    def _web_ambience(self, model3d):
        """L'AMBIANCE de la pièce ouverte — l'éclairage sous lequel elle se montre.

        ─ Pourquoi elle passe par ICI et pas par un `read` du navigateur ────────

        ⚠️ **Un visiteur n'a de droit sur aucun de ces modèles.** Dans l'éditeur, le trajet
        est entièrement client : `load_for_company` rend le catalogue, et la sidebar choisit.
        Ici il n'y a rien à choisir — le produit a SON ambiance — et rien à lire côté
        navigateur. D'où ce montage serveur, en `sudo`, exactement comme les zones de
        matière et pour la même raison.

        ⓘ Le vocabulaire vient de `js_row()`, dans `product_editor` : la table de
        correspondance `snake_case` → `camelCase` n'existe qu'à un seul endroit. La recopier
        ici en ferait une seconde, et un champ ajouté d'un côté manquerait de l'autre — le
        symptôme serait un réglage qui marche dans l'éditeur et pas sur le site ([[L-073]]).

        ─ Ce qui reste VOLONTAIREMENT sans garde-fou ───────────────────────────

        ⚠️ **Le reflet au sol et la photo d'environnement passent tels quels**, alors qu'ils
        coûtent cher sur un téléphone — un rendu complet de la scène par image pour l'un,
        deux à vingt mégaoctets à télécharger pour l'autre.

        C'est un arbitrage de Gerry (2026-09-18) : *« les rendre disponibles sur mobile si
        c'est ce que veut celui qui a édité la scène »*. Les filtrer ici aurait été plus
        simple à écrire et faux à l'usage — un présentoir de bijoux vaut peut-être son reflet
        au sol même sur un téléphone, et personne d'autre que l'auteur de la scène ne peut en
        juger. L'éditeur AVERTIT à la place, dans son onglet Rendu.

        ⓘ Absente, le viewer retombe sur ses constantes mesurées — c'est-à-dire sur le rendu
        d'avant ce chantier, jamais sur du noir. Un produit dont personne n'a choisi
        l'ambiance s'affiche donc exactement comme hier.
        """
        self.ensure_one()
        if not model3d:
            return None
        preset = model3d.sudo().render_preset_id
        return preset.js_row() if preset else None

    def _web_scene_models(self, definition):
        """Les pièces de la scène, LUES DE LA DÉFINITION — jamais recomposées.

        ⓘ La définition sait de quelle pièce vient chaque nœud (`model3dId`), y
        compris après une permutation (D-164). Rejouer les échanges ici pour le
        deviner donnerait une seconde lecture de la même chose, et c'est
        exactement ce qui finit par diverger.
        """
        models = []
        pile = [definition] if definition else []
        while pile:
            node = pile.pop()
            if not isinstance(node, dict):
                continue
            model_id = node.get("model3dId")
            if model_id and model_id not in models:
                models.append(model_id)
            pile.extend(node.get("children") or [])
        return models

    def _web_materials(self, material_ids):
        """Les fiches matière, ENTIÈRES — et c'est délibéré.

        ⚠️ Le viewer lit une trentaine de champs PBR, dont la liste vit en JS
        (`PBR_READ_FIELDS`) sous sa propre garde. La recopier ici en ferait une
        seconde, et un champ ajouté d'un côté manquerait de l'autre — ce qui
        s'est déjà produit **dans le seul monde JS** (`normal_scale`,
        `ao_map_intensity`, `bump_scale` : rendu muet, deux écrans qui diffèrent).
        On envoie donc **tout l'enregistrement** : rien à tenir à jour.

        ⓘ `bin_size` : les binaires voyagent en TAILLE, pas en contenu — les
        textures sont des `Many2one`, et le viewer va chercher leurs images par
        URL. C'est exactement ce que fait l'éditeur.
        """
        if not material_ids:
            return {}
        rows = self.env["product.model3d.material"].sudo().with_context(
            bin_size=True,
        ).browse(list(material_ids)).read()
        return {row["id"]: row for row in rows}

    def _web_zones(self, model3d, definition, values):
        """Les zones de matière de toute la scène, et ce qu'elles rendent.

        ⚠️ **La page ne peut pas les lire elle-même.** Dans l'éditeur, ce trajet
        est entièrement CLIENT : `searchRead` des zones, `resolve_zone_materials`,
        `read` des fiches, exceptions par placement. Un visiteur public n'a de
        droit sur aucun de ces modèles — d'où ce montage serveur, en `sudo`, qui
        rend la même chose.

        ⓘ Les deux résolutions sont déjà en Python (`resolve_zone_materials`,
        `resolve_placement_exceptions`) : l'éditeur ne fait que les appeler. On
        les appelle aussi, avec les mêmes réponses — donc une matière PILOTÉE par
        une question (D-166) suit la configuration ici comme là-bas.
        """
        self.ensure_one()
        empty = {"zonesByPiece": {}, "nodeMaterials": {}}
        model_ids = self._web_scene_models(definition)
        if not model_ids:
            return empty
        Zone = self.env["product.model3d.material.zone"].sudo()
        rows = Zone.search_read(
            [("model3d_id", "in", model_ids)],
            ["id", "name", "face_keys", "face_role", "material_id", "origin",
             "sequence", "model3d_id", "driver_attribute_id", "file_material"],
            order="sequence, id",
        )
        pieces = self.env["product.model3d"].sudo().browse(model_ids)
        # La matière RENDUE d'une zone pilotée dépend des réponses : c'est le
        # cœur de D-166, et c'est ce qui rend une matière configurable.
        rendered = {}
        for piece in pieces:
            try:
                rendered.update(piece.resolve_zone_materials(values) or {})
            except Exception:  # noqa: BLE001
                # ⓘ Le défaut de la zone reste en place : une correspondance
                # illisible ne doit pas rendre la pièce noire (esprit de D-150).
                continue

        zones_by_piece = {str(model_id): [] for model_id in model_ids}
        needed = set()
        for row in rows:
            model_id = row["model3d_id"][0] if row["model3d_id"] else None
            default_id = row["material_id"][0] if row["material_id"] else None
            render_id = rendered.get(row["id"], rendered.get(str(row["id"]), default_id))
            if render_id:
                needed.add(render_id)
            zones_by_piece.setdefault(str(model_id), []).append({
                "id": row["id"],
                "name": row["name"],
                # ⚠️ Le MÊME filtre que côté client et côté Python : une chaîne
                # NON VIDE. Une face au nom vide ne se résout nulle part.
                "faceKeys": [k for k in (row["face_keys"] or []) if k],
                "faceRole": row["face_role"] or None,
                "auto": row["origin"] == "auto",
                "fileMaterial": bool(row["file_material"]),
                "materialId": default_id,
                "renderMaterialId": render_id,
            })

        # Les EXCEPTIONS par placement (D-175) : deux barreaux du même lien
        # peuvent rendre autre chose.

        # ── PAR POSE : ce que CHAQUE pièce répond (D-368) ───────────────────
        #
        # ⚠️ Ce qui précède résout une zone par PIÈCE, avec les réponses de la RACINE. Une
        # pièce posée répond pourtant à SES questions : elle SUIT la racine, ou son lien
        # la fixe, ou le client l'a choisie pour elle seule (D-332). Sans ce calque, le
        # bumper du JeNo resterait à la couleur générale quand le client lui en donne une
        # autre — exactement ce que l'éditeur évite avec `_resolveZoneMaterialsByNode`.
        # ⓘ Le calque ne porte que les ÉCARTS, et le viewer le lit déjà
        # (`zoneMaterialsByNode`, `_zoneMaterialFor`).
        overlay_ids = self._web_zone_overrides_by_node(model3d, definition, values, rows, rendered)
        for by_zone in overlay_ids.values():
            needed.update(material_id for material_id in by_zone.values() if material_id)

        materials = self._web_materials(needed)
        for zones in zones_by_piece.values():
            for zone in zones:
                zone["material"] = materials.get(zone["renderMaterialId"]) or None
        return {
            "zonesByPiece": zones_by_piece,
            # Par ID : la page y puise sans que la même fiche voyage deux fois.
            "materials": materials,
            "byNode": {
                node_id: {str(zone_id): (materials.get(material_id) or None) if material_id else None
                          for zone_id, material_id in by_zone.items()}
                for node_id, by_zone in overlay_ids.items()
            },
        }

    def _web_zone_overrides_by_node(self, model3d, definition, values, rows, rendered):
        """`{nodeId → {zoneId → matière | None}}` — les poses qui rendent AUTRE chose que
        leur pièce, parce qu'elles répondent autre chose que la racine (D-368).

        ⓘ Groupé par (pièce, réponses aux questions PILOTES) : dix vis d'une même teinte
        coûtent une résolution, pas dix — la règle du calque de l'éditeur.
        """
        driven = {}
        for row in rows:
            if row["driver_attribute_id"] and row["model3d_id"]:
                driven.setdefault(row["model3d_id"][0], []).append(row)
        if not driven or not model3d:
            return {}
        Model3d = self.env["product.model3d"].sudo()
        answers_by_node = Model3d._node_answers(definition, model3d.get_attribute_scope(values))
        marker = Model3d.ATTRIBUTE_MARKER
        groups = {}

        def walk(node):
            for child in node.get("children") or []:
                piece_id = child.get("model3dId")
                if piece_id in driven and child.get("id") in answers_by_node:
                    drivers = {r["driver_attribute_id"][0] for r in driven[piece_id]}
                    answers = {
                        int(key[len(marker):]): value
                        for key, value in answers_by_node[child["id"]].items()
                        if key.startswith(marker) and int(key[len(marker):]) in drivers
                    }
                    signature = (piece_id, tuple(sorted(answers.items())))
                    groups.setdefault(signature, []).append(child["id"])
                walk(child)

        walk(definition or {})
        out = {}
        for (piece_id, answers), node_ids in groups.items():
            try:
                resolved = Model3d.browse(piece_id).resolve_zone_materials(dict(answers)) or {}
            except Exception:  # noqa: BLE001 — une correspondance illisible ne noircit rien (D-150)
                continue
            for row in driven[piece_id]:
                if row["id"] not in resolved and str(row["id"]) not in resolved:
                    continue
                material_id = resolved.get(row["id"], resolved.get(str(row["id"]))) or None
                default_id = row["material_id"][0] if row["material_id"] else None
                if material_id == rendered.get(row["id"], rendered.get(str(row["id"]), default_id)):
                    continue
                for node_id in node_ids:
                    out.setdefault(node_id, {})[row["id"]] = material_id
        return out

    def _web_camera(self, model3d):
        """La vue PAR DÉFAUT de la pièce — celle d'où sa vignette a été prise.

        ⓘ C'est tout l'intérêt de D-115 : *« la vue depuis laquelle on veut
        travailler est la vue que l'on veut montrer »*. Un seul drapeau pour les
        deux, donc **l'image du produit et la 3D se superposent** — la page peut
        montrer la photo pendant le chargement, puis se poser exactement dessus
        (demande de Gerry, 2026-09-06).

        ⚠️ La reproductibilité vient de la POSE REJOUÉE, pas de bornes figées :
        c'est ce que dit `is_thumbnail`, et c'est pourquoi on envoie la pose et
        non un cadrage.
        """
        if not model3d:
            return None
        camera = self.env["product.model3d.camera"].sudo().search(
            [("model3d_id", "=", model3d.id), ("is_thumbnail", "=", True)], limit=1,
        )
        return self._web_camera_view(camera)

    def _web_camera_view(self, camera, definition=None):
        """Une vue enregistrée, dans la forme que le viewer applique — `None` sans vue.

        ⓘ Partagée par la vue par défaut et par celle d'une ÉTAPE (D-385) : deux
        sérialisations d'une même fiche divergeraient au premier champ ajouté.
        """
        if not camera:
            return None
        return {
            "pose": {
                "azimuth": camera.pos_azimuth,
                "inclination": camera.pos_inclination,
                "distance": camera.pos_distance,
            },
            "fov": camera.fov,
            "projection": camera.projection,
            "fitDistance": camera.fit_distance,
            # ⚠️ **LES BORNES — la page ne les servait pas** (Gerry, 2026-10-01 : « les limites
            # définies pour la caméra ne sont pas prises en compte »). Le viewer bornait bien,
            # mais seulement ce qu'on lui donnait. Les distances partent en FACTEURS, telles
            # qu'en base (`distanceIn`) : le rayon qui les convertit en millimètres dépend de
            # la scène et du canevas, que seul le viewer connaît (D-389).
            "limits": {
                "azimuthMin": camera.azimuth_min,
                "azimuthMax": camera.azimuth_max,
                "inclinationMin": camera.inclination_min,
                "inclinationMax": camera.inclination_max,
                "distanceMin": camera.distance_min,
                "distanceMax": camera.distance_max,
                "distanceIn": "factor",
            },
            # ⓘ LA CIBLE fait partie de la vue (D-116). Sans elle, la page posait la
            # pose sans centre — et une pièce isolée puis quittée gardait le centre de
            # la pièce. Gerry (2026-09-23) : « lorsque l'on quitte, il faut revenir à
            # la vue caméra en cours, qui donnera la target ».
            "target": self._web_camera_target(camera, definition),
        }

    def _web_camera_target(self, camera, definition=None):
        """La cible d'une vue, telle que le viewer la résout : un NŒUD `c<linkId>`, la
        MATIÈRE (`root`) ou l'ORIGINE. Miroir de `_resolveCameraTarget` de l'éditeur —
        `root` et `origin` ne sont pas la même chose (D-116)."""
        if camera.target_kind == "piece" and camera.target_link_id:
            # ⚠️ L'identité du NŒUD que le lien pose, lue dans la définition (D-349) : un
            # lien imbriqué s'appelle `c10/c11`, et `c<lien>` ne le trouverait pas.
            return {"nodeId": self._web_node_id_of_link(camera.target_link_id, definition)}
        if camera.target_kind == "root":
            return {"root": True}
        return {"origin": True}

    def _web_node_id_of_link(self, link, definition=None):
        """Le nœud de la PREMIÈRE pose d'un lien dans la définition — `c<lien>` à défaut,
        l'identité d'un enfant direct. Une caméra vise une place, pas une pose.

        ⓘ `definition` : celle que l'appelant a déjà calculée — c'est l'objet le plus cher
        de la réponse, et les vues des étapes la demanderaient une fois chacune."""
        if definition is None:
            model3d = self._web_model3d()
            definition = model3d.to_definition() if model3d else None

        def walk(node):
            for child in (node or {}).get("children") or []:
                if child.get("linkId") == link.id:
                    return child.get("id")
                hit = walk(child)
                if hit:
                    return hit
            return None

        return walk(definition) or "c%d" % link.id

    def _web_image(self):
        """L'image du produit — ce qu'on montre PENDANT que la 3D se construit.

        ⓘ Une URL, pas des octets : elle passe par le cache du navigateur et ne
        gonfle pas une réponse que l'on renvoie à chaque clic.

        ⚠️ **PAS `/web/image` — le visiteur n'a aucun droit sur ce produit.** Ce
        contrôleur vérifie la lecture de l'enregistrement : un produit non publié
        rendait donc le pictogramme d'Odoo, et l'attente montrait un appareil
        photo barré au lieu de la pièce (relevé le 2026-09-07). C'est le même mur
        que celui des vignettes de valeurs, franchi de la même façon : une route
        à nous, en `sudo` (D-258).

        ⓘ **La route est indexée par le JETON, pas par le produit** : il autorise
        exactement cette configuration, et rien d'autre. Une route par
        identifiant de produit ouvrirait tout le catalogue à qui essaie des
        numéros.
        """
        self.ensure_one()
        if not self.product_tmpl_id.image_1920:
            return None
        self._ensure_access_token()
        return "/configurator/%s/image" % self.access_token

    def _web_link_answers(self):
        """`{lien → {attribut → réponse}}` — ce que le moteur attend PAR PLACEMENT (D-332).

        ⚠️ La même règle de forme que `_web_values` : une question NUMÉRIQUE reçoit le NOM
        de la valeur (l'identifiant y entrerait comme un nombre faux, [[L-219]] côté 3D),
        une DISCRÈTE son identifiant. Une valeur disparue n'entre pas.
        """
        self.ensure_one()
        Value = self.env["product.attribute.value"]
        out = {}
        for link_key, answers in (self.child_values or {}).items():
            try:
                link_id = int(link_key)
            except (TypeError, ValueError):
                continue
            resolved = {}
            for attr_key, value_id in (answers or {}).items():
                value = Value.browse(int(value_id)).exists() if value_id else Value
                if not value:
                    continue
                resolved[value.attribute_id.id] = (
                    value.name if value.attribute_id.is_numeric() else value.id
                )
            if resolved:
                out[link_id] = resolved
        # ⚠️ **LES SAISIES D'UN PLACEMENT ENTRENT AUSSI** (D-353) — sans quoi une cote
        # tapée pour un enfant n'atteindrait jamais sa géométrie. La saisie rangée est
        # déjà la forme brute que `to_scope_entry` sait lire (le nombre nu, D-160).
        for link_key in (self.child_custom_values or {}):
            try:
                link_id = int(link_key)
            except (TypeError, ValueError):
                continue
            typed = self._web_child_custom(link_id)
            if typed:
                out.setdefault(link_id, {}).update(typed)
        return out

    def _web_placements(self, model3d, definition, values):
        """Les PLACEMENTS que le client peut régler — `{nodeId → {linkId, label,
        questions}}` — et eux seuls (D-332, D-333).

        ⚠️ **La vérité de « sélectionnable » vient de la DÉFINITION** (`editableAttributeIds`,
        posé par l'éditeur : les questions du gabarit que l'auteur n'a pas fixées). La
        redire ici ferait deux règles pour une même pièce ([[L-034]]). Un placement sans
        question éditable n'apparaît pas : le rail piloté par son parent ne se sélectionne
        pas, et le survol ne le nomme pas (arbitrage Gerry, 2026-09-23).

        ⓘ Les questions ont la MÊME forme que celles de la racine (`_web_attribute_lines`) :
        la page les rend avec le code qu'elle a déjà. La disponibilité se demande au même
        évaluateur, sur le gabarit de l'ENFANT et ses propres réponses.
        """
        self.ensure_one()
        if not definition:
            return {}
        Model3d = self.env["product.model3d"].sudo()
        Session = self.env["product.config.session"].sudo()
        variants = model3d._resolve_swap_variants(values) if model3d else {}
        child_values = self.child_values or {}
        # ⓘ D-368 — ce que chaque pièce RÉPOND, par la pile du moteur relue au serveur :
        # défauts, variante désignée, réponse SUIVIE d'un ancêtre, réponse du lien et du
        # client. Sans elle, la page cocherait la couleur par défaut d'un bumper que le
        # moteur construit à la couleur du JeNo.
        answers_by_node = Model3d._node_answers(
            definition, model3d.get_attribute_scope(values) if model3d else {})
        out = {}

        def walk(node):
            for child in node.get("children") or []:
                editable = child.get("editableAttributeIds") or []
                link_id = child.get("linkId")
                if editable and link_id:
                    out[child["id"]] = self._web_placement(
                        Model3d, Session, child, link_id, editable,
                        child_values.get(str(link_id)) or child_values.get(link_id) or {},
                        variants, answers_by_node.get(child["id"]) or {})
                walk(child)

        walk(definition)
        return out

    def _web_placement(self, Model3d, Session, node, link_id, editable, answers, variants,
                       resolved=None):
        piece = Model3d.browse(node.get("model3dId")).exists()
        link = self.env["product.model3d.component"].sudo().browse(link_id).exists()
        tmpl = piece.product_tmpl_id
        variant = link._swapped_variant(variants) if link else None
        by_attr = {
            ptav.attribute_id.id: ptav.product_attribute_value_id.id
            for ptav in (variant.product_template_attribute_value_ids if variant else [])
        }
        # ⓘ Une question répondue par SAISIE n'a pas de valeur cochée : la pile
        # ci-dessous retomberait sinon sur la variante ou le défaut, et la page
        # montrerait deux réponses à la fois (D-353).
        typed = self._web_child_custom(link_id)
        # Ce que le client a choisi, sinon ce que la pièce RÉPOND (`resolved` : la pile du
        # moteur, suivi compris — D-368), sinon la VARIANTE désignée, sinon le défaut de la
        # ligne.
        resolved = resolved or {}
        chosen_ids = []
        for line in tmpl.attribute_line_ids:
            attr_id = line.attribute_id.id
            if attr_id in typed:
                continue
            picked = (answers.get(str(attr_id)) or answers.get(attr_id)
                      or self._web_value_of_entry(
                          line, resolved.get(line.attribute_id.scope_key()))
                      or by_attr.get(attr_id)
                      or (line.default_val.id if "default_val" in line._fields and line.default_val else None))
            if picked:
                chosen_ids.append(int(picked))
        questions = []
        for line in tmpl.attribute_line_ids.sorted():
            if line.attribute_id.id not in editable:
                continue
            values = self._web_offered_values(line)
            try:
                available = set(Session.values_available(
                    check_val_ids=values.ids, value_ids=list(chosen_ids),
                    custom_vals=self._web_parsed_custom(typed),
                    product_tmpl_id=tmpl.id, product_template_attribute_line_id=line.id))
            except Exception:  # noqa: BLE001 — un évaluateur qui tombe ne doit pas cacher la question
                _logger.warning("placement %s: availability could not be evaluated", link_id,
                                exc_info=True)
                available = set(values.ids)
            values = self._web_shown_values(line, values, available, chosen_ids)
            categories, category_keys = self._web_categorized(values)
            questions.append({
                "id": line.attribute_id.id,
                "name": line.attribute_id.name,
                "required": bool(line.required),
                "multi": bool(line.multi),
                "free": self._web_free_field(line),
                "customValue": typed.get(line.attribute_id.id),
                "displayType": line.attribute_id.display_type,
                "swatchMark": line.attribute_id.swatch_mark,
                "answerSize": line.attribute_id.answer_size,
                "answerLayout": line.attribute_id._web_answer_layout(),
                "categories": categories,
                "values": [{
                    "id": value.id,
                    "name": value.display_value or value.name,
                    "raw": value.name,
                    "available": value.id in available,
                    "chosen": value.id in chosen_ids,
                    "categoryKeys": category_keys[value.id],
                    "color": value.html_color or None,
                    "image": ("/configurator/value/%s/image" % value.id
                              if self._web_value_has_image(value) else None),
                } for value in values],
            })
        return {
            "nodeId": node["id"],
            "linkId": link_id,
            "label": node.get("label") or tmpl.display_name or "",
            "questions": questions,
        }

    def web_set_child_value(self, link_id, value):
        """Répondre à une question d'un PLACEMENT — D-332.

        ⚠️ Refusé si la question n'est pas ÉDITABLE pour ce lien : c'est la définition qui
        le dit, et un client ne défait pas ce que l'auteur a fixé. Une question à réponses
        MULTIPLES bascule la valeur ; les autres la remplacent.
        """
        self.ensure_one()
        model3d = self._web_model3d()
        values = self._web_values()
        definition = model3d.to_definition(values, link_answers=self._web_link_answers()) if model3d else None
        placements = self._web_placements(model3d, definition, values)
        # ⚠️ Par le LIEN, jamais par un `c<lien>` recomposé : les placements sont rangés
        # sous l'id du nœud, qui porte le chemin de sa pose quand il est imbriqué
        # (D-349, `c10/c11`). Deux poses d'un même sous-assemblage partagent le lien de
        # leurs enfants, et donc leurs réponses (D-332, v1) — la première suffit.
        placement = next((p for p in placements.values()
                          if p.get("linkId") == int(link_id)), None)
        question = next((q for q in (placement or {}).get("questions", [])
                         if q["id"] == value.attribute_id.id), None)
        if not question:
            return {"error": "unknown_value"}
        answers = dict((self.child_values or {}).get(str(int(link_id))) or {})
        key = str(value.attribute_id.id)
        if question["multi"]:
            current = answers.get(key)
            kept = list(current) if isinstance(current, list) else ([current] if current else [])
            answers[key] = ([v for v in kept if v != value.id] if value.id in kept
                            else kept + [value.id])
        else:
            answers[key] = value.id
        child_values = dict(self.child_values or {})
        child_values[str(int(link_id))] = answers
        self.write({"child_values": child_values})
        # ⓘ Un `write` sur `value_ids` prévient ceux qui regardent ; celui-ci doit le faire
        # de lui-même — le même signal (L-451).
        self._notify_configuration_changed()
        return self.web_state()

    def _web_confirm_children(self):
        """La VARIANTE des pièces posées naît à la confirmation — D-332, D-368.

        Le même geste que pour la racine (D-190) : un gabarit, des réponses, une variante.
        ⓘ Deux sortes de pièces la reçoivent : celle que le client a RÉPONDUE (D-332), et
        celle qu'une question VENDUE À PART permute (D-368) — touchée ou non, elle part sur
        sa propre ligne de devis, et il lui faut un article.

        ⚠️ **LA COMBINAISON EST COMPLÈTE** : chaque question du gabarit reçoit la réponse que
        la pièce DONNE (`_node_answers` — défaut, variante désignée, suivi, lien, client).
        Avant D-368 on n'envoyait que les questions éditables et les valeurs fixées : une
        question SUIVIE manquait, la combinaison était incomplète, et aucune variante ne
        naissait — sans erreur visible (l'écart de D-332).

        ⚠️ Une variante qui ne peut pas naître est consignée, jamais bloquante : la
        confirmation de la racine ne dépend pas d'un enfant.
        """
        self.ensure_one()
        model3d = self._web_model3d()
        if not model3d:
            return {}
        values = self._web_values()
        definition = model3d.to_definition(values, link_answers=self._web_link_answers())
        Model3d = self.env["product.model3d"].sudo()
        answers_by_node = Model3d._node_answers(definition, model3d.get_attribute_scope(values))
        apart = self.product_tmpl_id._sale_separately_attribute_ids()
        Link = self.env["product.model3d.component"].sudo()
        born = {}

        def children(node):
            for child in node.get("children") or []:
                yield child
                yield from children(child)

        for node in children(definition or {}):
            link_id = node.get("linkId")
            if not link_id or str(link_id) in born:
                continue
            typed = self._web_child_custom(link_id)
            answered = (self.child_values or {}).get(str(link_id)) or typed
            link = Link.browse(link_id).exists()
            sold = bool(link and link.swap_attribute_id.id in apart)
            if not (answered or sold):
                continue
            tmpl = Model3d.browse(node.get("model3dId")).product_tmpl_id
            if not tmpl:
                continue
            value_ids = self._web_child_value_ids(
                tmpl, answers_by_node.get(node.get("id")) or {}, typed, node, link_id)
            variant = self._web_child_variant(tmpl, value_ids, link_id)
            if variant:
                born[str(link_id)] = variant.id
        if born:
            self.write({"child_variants": born})
        return born

    def _web_child_value_ids(self, tmpl, resolved, typed, node, link_id):
        """Les valeurs de la combinaison d'une pièce : une par question de son gabarit."""
        marker = self.env["product.model3d"].ATTRIBUTE_MARKER
        formulas = {str(key) for key, binding in (node.get("attributeOverrides") or {}).items()
                    if isinstance(binding, dict) and "expr" in binding}
        value_ids = []
        for line in tmpl.attribute_line_ids:
            attribute = line.attribute_id
            # ⓘ **La saisie devient une VALEUR ICI, à la confirmation** (D-353) — réutilisée
            # si elle existe, créée sinon, rattachée à la ligne de l'enfant. Un attribut
            # `no_variant` n'en fait pas : sa saisie reste dans la session.
            if attribute.id in typed:
                if attribute._resolves_to_values():
                    value = line.resolve_custom_value(typed[attribute.id])
                    if value:
                        value_ids.append(value.id)
                continue
            if str(attribute.id) in formulas:
                # ⚠️ Une FORMULE ne se résout qu'au moteur : la pièce prend la réponse d'en
                # dessous (son défaut, sa variante). Dit dans le journal, pas en silence.
                _logger.info("placement %s: “%s” is computed by a formula; its variant takes "
                             "the answer below it", link_id, attribute.display_name)
            value_id = self._web_value_of_entry(line, resolved.get(marker + str(attribute.id)))
            if value_id:
                value_ids.append(value_id)
        return value_ids

    def _web_child_variant(self, tmpl, value_ids, link_id):
        """La variante de cette combinaison — retrouvée, sinon créée — ou rien.

        ⓘ **Par le cœur d'Odoo, pas par une session de l'enfant.** La recherche de variante
        d'OCA (`search_variant`) ne retrouve pas celles qu'Odoo engendre lui-même à la
        création des lignes d'attribut : elle en CRÉAIT une seconde, et la contrainte
        d'unicité de la combinaison tombait au vidage — mesuré. Le cœur sait retrouver une
        combinaison (`_get_variant_for_combination`) et la créer pour un attribut
        dynamique (`_create_product_variant`).

        ⚠️ **SOUS UN POINT DE SAUVEGARDE, et VIDÉ avant d'être retenu** : une erreur SQL
        attrapée sans point de sauvegarde laisse la transaction en échec, et un identifiant
        retenu avant le vidage désigne une ligne qu'un repli a effacée.
        """
        wanted = set(value_ids)
        combination = tmpl.attribute_line_ids.product_template_value_ids.filtered(
            lambda ptav: ptav.product_attribute_value_id.id in wanted)
        try:
            with self.env.cr.savepoint():
                variant = (tmpl._get_variant_for_combination(combination)
                           or tmpl._create_product_variant(combination, log_warning=True))
                if not variant:
                    raise ValueError("no variant for this combination")
                self.env.flush_all()
            return variant
        except Exception:  # noqa: BLE001
            _logger.warning("placement %s: the child variant could not be born", link_id,
                            exc_info=True)
            return self.env["product.product"]

    def web_separate_lines(self, definition=None):
        """Les lignes de devis À PART de cette configuration — D-368.

        `[{attributeId, valueId, linkId, name, productId, qty, price}]` : une par question
        vendue à part dont la réponse désigne un produit. « Sans bumper » (sans produit)
        n'en donne aucune.

        ⓘ **L'article et son prix** : la variante née à la confirmation (`child_variants`) ;
        avant, celle de la COMBINAISON que la pièce répond (sa matière comprise — la couleur
        du bumper change son prix si la valeur porte un supplément), sinon celle que la
        valeur désigne.

        ⓘ **La quantité** (D-375) : le nombre de POSES des liens permutés par la question,
        répétitions et miroirs compris — le moteur les compte, dans Node
        (`product.model3d._count_poses`). Une pose RÉFLÉCHIE d'une pièce chirale qui a un
        jumeau passe sur une ligne à part, sous l'article du jumeau (D-074, D-357). Sans
        décompte (Node absent), la quantité d'avant : le nombre de liens — dit au journal.
        """
        self.ensure_one()
        apart = self.product_tmpl_id._sale_separately_attribute_ids()
        if not apart:
            return []
        model3d = self._web_model3d()
        values = self._web_values()
        if definition is None and model3d:
            definition = model3d.to_definition(values, link_answers=self._web_link_answers())
        Model3d = self.env["product.model3d"].sudo()
        Link = self.env["product.model3d.component"].sudo()
        answers_by_node = (Model3d._node_answers(definition, model3d.get_attribute_scope(values))
                           if model3d else {})
        nodes_by_attr = {}

        def walk(node):
            for child in node.get("children") or []:
                link = Link.browse(child.get("linkId") or 0).exists()
                if link and link.swap_attribute_id.id in apart:
                    nodes_by_attr.setdefault(link.swap_attribute_id.id, []).append(child)
                walk(child)

        walk(definition or {})
        poses = None
        if model3d and nodes_by_attr:
            poses = Model3d._count_poses(definition, model3d.get_attribute_scope(values))
            if poses is None:
                _logger.warning("session %s: the engine did not count the poses; parts sold "
                                "separately are counted one per placement", self.id)
        variants = self.child_variants or {}
        Product = self.env["product.product"].sudo()
        # ⚠️ **LA MÊME LISTE DE PRIX QUE LE PRODUIT** (`get_cfg_price`) : sans elle, la page
        # annonçait le bumper au prix catalogue (1,00) et le panier le facturait à 0,00 —
        # mesuré sur une copie de fabk18, dont la liste « Par défaut » porte des règles.
        pricelist = self.env.user.partner_id.property_product_pricelist
        out = []
        for value in self.value_ids.filtered(lambda v: v.attribute_id.id in apart):
            if not value.product_id:
                continue
            nodes = nodes_by_attr.get(value.attribute_id.id) or []
            straight, reflected = self._web_pose_counts(nodes, poses)
            product, price, name = value.product_id.sudo(), None, None
            twin = None
            if nodes:
                node = nodes[0]
                link_id = node.get("linkId")
                model = Model3d.browse(node.get("model3dId")).exists()
                tmpl = model.product_tmpl_id
                value_ids = []
                if tmpl:
                    value_ids = self._web_child_value_ids(
                        tmpl, answers_by_node.get(node.get("id")) or {},
                        self._web_child_custom(link_id), node, link_id)
                if str(link_id) in variants:
                    product = Product.browse(variants[str(link_id)])
                elif tmpl:
                    found, price, name = self._web_combination(tmpl, value_ids, pricelist)
                    # ⚠️ Sans variante encore née, AUCUN article : retomber sur celui de
                    # la valeur afficherait « Bumper (Bleu) » au prix du Rouge.
                    product = found or self.env["product.product"]
                if reflected:
                    twin = self._web_twin_line(model, value_ids, str(link_id) in variants,
                                               pricelist, link_id)
                if not twin:
                    straight, reflected = straight + reflected, 0
            base = {"attributeId": value.attribute_id.id, "valueId": value.id,
                    "linkId": nodes[0].get("linkId") if nodes else None}
            # ⓘ Toujours au moins une : une pièce choisie se vend, même sans pose
            # dans la scène (option sans 3D, nature ④).
            if straight or not twin:
                out.append(dict(base,
                                name=product.display_name if product else name,
                                productId=product.id or None,
                                qty=max(straight, 1),
                                price=price if price is not None
                                else self._web_price(product, pricelist)))
            if twin:
                out.append(dict(base, mirrored=True, qty=reflected, **twin))
        return out

    @api.model
    def _web_pose_counts(self, nodes, poses):
        """`(droites, réfléchies)` — les poses de ces nœuds, ou un par nœud sans décompte."""
        if poses is None:
            return len({n.get("linkId") for n in nodes}), 0
        keys = {n.get("id") for n in nodes}
        mine = [p for p in poses if p.get("sourceKey") in keys]
        reflected = sum(1 for p in mine if p.get("mirrored"))
        return len(mine) - reflected, reflected

    def _web_twin_line(self, model, value_ids, confirmed, pricelist, link_id):
        """L'article de l'IMAGE d'une pièce chirale — `{name, productId, price}`, ou rien.

        ⓘ **La règle de l'éditeur** (`_imageArticle`, D-357) : une pièce `chiral` qui a un
        jumeau (`mirror_source_id`) a pour image ce jumeau ; réversible, ou chirale sans
        jumeau encore, elle-même — rien à scinder. Le jumeau reçoit la MÊME combinaison :
        la matière suit le parent sur les deux côtés (R2), un gant gauche rouge a pour image
        un gant droit rouge.

        ⚠️ Sa variante ne NAÎT qu'une fois la pièce confirmée — comme celle de l'original :
        afficher un prix ne crée pas d'article.
        """
        if not model or model.reversible != "chiral":
            return None
        twin_tmpl = self.env["product.model3d"].sudo().search(
            [("mirror_source_id", "=", model.id)], limit=1).product_tmpl_id
        if not twin_tmpl:
            return None
        if confirmed:
            product = self._web_child_variant(twin_tmpl, value_ids, link_id)
            return {"name": product.display_name if product else twin_tmpl.display_name,
                    "productId": product.id or None,
                    "price": self._web_price(product or twin_tmpl, pricelist)}
        found, price, name = self._web_combination(twin_tmpl, value_ids, pricelist)
        return {"name": found.display_name if found else name,
                "productId": found.id or None,
                "price": price if price is not None else self._web_price(found, pricelist)}

        return out

    def _web_no_variant_ptav_ids(self):
        """Les `product.template.attribute.value` de TOUTES les réponses « sans variante » —
        celles qui vont sur la LIGNE de commande, et non dans l'article (W-99 / D-393).

        ⚠️ Depuis l'option A, l'article ne porte plus ces réponses : une seule qui ne serait
        pas transmise, et la boutique y mettrait d'office la PREMIÈRE valeur (« Mat » au lieu
        de « Brillant », mesuré). Les questions vendues à part (D-368) en sont un cas.
        """
        self.ensure_one()
        chosen = self.value_ids.filtered(lambda v: v.attribute_id.create_variant == "no_variant")
        if not chosen:
            return []
        return self.product_tmpl_id.attribute_line_ids.product_template_value_ids.filtered(
            lambda ptav: ptav.product_attribute_value_id in chosen).ids

    @api.model
    def _web_price(self, product, pricelist):
        """Le prix d'un article (ou d'un gabarit) par la liste de prix donnée, sinon catalogue."""
        if pricelist:
            return pricelist._get_product_price(product, 1.0)
        return product._get_contextual_price()

    @api.model
    def _web_combination(self, tmpl, value_ids, pricelist=None):
        """`(variante existante | vide, prix, nom)` d'une combinaison — SANS créer la variante.

        ⓘ Une variante dynamique n'existe qu'une fois commandée : afficher un prix ne doit
        pas en créer une. Sans elle, le prix est celui du gabarit plus les suppléments de
        la combinaison, par la liste de prix — la même voie que `get_cfg_price`
        (`current_attributes_price_extra`).
        """
        wanted = set(value_ids)
        combination = tmpl.attribute_line_ids.product_template_value_ids.filtered(
            lambda ptav: ptav.product_attribute_value_id.id in wanted)
        variant = tmpl._get_variant_for_combination(combination)
        if variant:
            return variant, self._web_price(variant, pricelist), variant.display_name
        extra = sum(combination.mapped("price_extra"))
        # ⓘ Le nom que la variante PORTERA — la règle du cœur (`_get_combination_name`).
        label = combination._get_combination_name()
        return (self.env["product.product"],
                self._web_price(tmpl.with_context(current_attributes_price_extra=[extra]),
                                pricelist),
                "%s (%s)" % (tmpl.display_name, label) if label else tmpl.display_name)

    @api.model
    def _web_placement_model_id(self, definition, node_id):
        found = None

        def walk(node):
            nonlocal found
            for child in node.get("children") or []:
                if child.get("id") == node_id:
                    found = child.get("model3dId")
                    return
                walk(child)

        walk(definition or {})
        return found

    @api.model
    def _web_value_of_entry(self, line, entry):
        """La VALEUR d'une ligne qui porte cette réponse de portée — ou rien — D-368.

        ⓘ Une entrée de portée est l'IDENTIFIANT de la valeur pour une question discrète, et
        le NOMBRE pour une question numérique (`to_scope_entry`, D-080). La page coche une
        valeur : on retrouve donc la valeur offerte qui porte ce nombre ou cet identifiant.
        Une réponse qu'aucune valeur offerte ne porte (une saisie, un nombre hors liste) ne
        coche rien — plutôt qu'une voisine plausible.
        """
        if entry is None or entry is False:
            return None
        values = line.value_ids
        if line.attribute_id.is_numeric():
            for value in values:
                try:
                    if float(str(value.name).replace(",", ".")) == float(entry):
                        return value.id
                except (TypeError, ValueError):
                    continue
            return None
        try:
            entry = int(entry)
        except (TypeError, ValueError):
            return None
        return entry if entry in values.ids else None

    @api.model
    def _web_placement_overrides(self, definition, node_id):
        found = {}

        def walk(node):
            nonlocal found
            for child in node.get("children") or []:
                if child.get("id") == node_id:
                    found = child.get("attributeOverrides") or {}
                    return
                walk(child)

        walk(definition or {})
        return found

    def _web_values(self):
        """`{attribut → réponse}` — la forme que le moteur 3D attend (D-163).

        ⚠️ **Une question NUMÉRIQUE reçoit le NOM de la valeur, jamais son
        identifiant.** `to_scope_entry` traduit une réponse numérique par
        `parse_number(brut)` : l'`id` de la valeur « 2 » y entrait comme **292**,
        un nombre parfaitement valide et faux. La plaque du JeNo se construisait
        donc à 292 mm d'épaisseur — relevé de Gerry le 2026-09-07, mesuré :
        `scope = {'__attribute_144': 292.0}`.

        ⓘ Le danger était ANNONCÉ, à un autre endroit : *« les options portent
        leur libellé, jamais leur identifiant »* (`answer_field`). La règle
        valait ici aussi, et rien ne la tenait.

        ⓘ Pour une question DISCRÈTE, l'identifiant reste la bonne forme : c'est
        lui que `resolve_answer` retrouve sans ambiguïté, là où deux valeurs
        peuvent porter le même libellé sur deux attributs différents.
        """
        self.ensure_one()
        values = {
            value.attribute_id.id: (
                value.name if value.attribute_id.is_numeric() else value.id
            )
            for value in self.value_ids
        }
        # ⚠️ **ET CE QUE LE CLIENT A TAPÉ** (D-353) — une largeur saisie doit changer la
        # pièce. Un nombre entre par sa forme rangée ; un TEXTE qui ne désigne aucune
        # valeur ne résout rien (`to_scope_entry` rend `None`) : sa clé reste hors de la
        # portée, et une condition qui le cite est ignorée plutôt que fausse (D-150).
        for attr_id, text in self._web_root_custom().items():
            values.setdefault(attr_id, text)
        return values

    def _web_missing_attributes(self, layout=None):
        """Les questions OBLIGATOIRES restées sans réponse, dans l'ordre affiché.

        ⚠️ **La visibilité passe AVANT l'exigence** — c'est la règle de D-086 :
        un attribut masqué par une condition cesse d'être obligatoire, et une
        ÉTAPE masquée emporte les siennes (`_web_step_layout`). Sans cela, une
        question que le client ne voit pas l'empêcherait de terminer, et rien à
        l'écran ne dirait pourquoi.

        ⚠️ **DES IDENTIFIANTS, PAS UN RECORDSET, pour `_is_visible`.** L'évaluateur
        fait `set(domaine) & set(value_ids)` : un recordset y donnait des
        enregistrements face à des entiers, l'intersection était toujours vide,
        et toute condition « in » passait pour fausse — une question obligatoire
        visible n'était pas réclamée ici, et la confirmation tombait plus loin,
        dans `validate_configuration`, sans dire laquelle manquait (relevé en
        préparant D-385). Les SAISIES aussi (`custom_vals`) : sans elles, une
        condition numérique n'était jamais vraie.

        ⓘ On ne s'appuie PAS sur `check_and_open_incomplete_step` : elle ne
        regarde que les ÉTAPES (`get_open_step_lines`), donc un produit qui n'en
        déclare aucune passerait sans contrôle.
        """
        self.ensure_one()
        chosen = self.value_ids
        custom_vals = self._get_custom_vals_dict()
        _steps, _step_of, hidden = layout or self._web_step_layout()
        # ⓘ Une question répondue par SAISIE est répondue (D-353) : sans cette ligne, une
        # largeur obligatoire tapée bloquerait la confirmation, faute de valeur cochée.
        typed = self._web_root_custom()
        missing = self.env["product.template.attribute.line"]
        for line in self.product_tmpl_id.attribute_line_ids.sorted():
            if not line.required or line in hidden:
                continue
            if not line._is_visible(value_ids=chosen.ids, custom_vals=custom_vals):
                continue
            if line.attribute_id.id in typed:
                continue
            if not (line._configurator_value_ids() & chosen):
                missing |= line
        return missing

    def _notify_configuration_changed(self):
        """Prévenir ceux qui regardent que la configuration a changé — D-253.

        ⚠️ **UN SIGNAL, PLUS L'ÉTAT COMPLET** ([[L-451]], 2026-09-29). Le message
        portait tout `web_state()` — environ 500 Ko sur le JeNo, définition 3D
        comprise — et il coûtait trois fois :
          · un second `web_state()` à CHAQUE clic, calculé dans le `write` (0,47 s
            sur 0,66 s au profil), en plus de celui de la réponse ;
          · une ligne d'environ 500 Ko dans `bus_bus` à chaque clic ;
          · un envoi websocket NON compressé à chaque spectateur — y compris à
            l'auteur, qui venait de recevoir le même état en réponse.

        Le signal nomme l'AUTEUR (le porteur de l'onglet qui a agi, `cfg_author`,
        posé par la route) : sa page l'ignore, les autres relisent
        `/configurator/state`, qui rend exactement ce qu'elles appliquaient. Sans
        auteur — une écriture du backend —, tout le monde relit.
        """
        self.ensure_one()
        self._bus_send("configurator_state",
                       {"author": self.env.context.get("cfg_author") or None})
        return super()._notify_configuration_changed()

    def _web_after_confirm(self):
        """Ce qui suit la confirmation, là où la configuration ATTERRIT.

        Vide ici, et c'est voulu : le cœur de l'interface ne sait pas ce qu'est
        un devis. `product_configurator_web_3d_sale` s'y branche pour écrire la
        ligne. Un autre atterrissage (un panier, une demande) s'y brancherait
        pareil, sans toucher à cette classe.
        """
        return True

    def _web_reopen_if_open_quote(self):
        """Rouvrir une configuration CONFIRMÉE tant que son devis n'est pas une commande — D-371.

        ⓘ **Rien n'est joué au stade du devis** (Gerry, 2026-09-29) : la variante d'une ligne
        n'est qu'un nom posé sur des réponses, et c'est la COMMANDE qui l'engage. D-190
        fermait la configuration dès sa confirmation ; c'est désormais la commande qui la
        verrouille.

        Sans le module de vente, rien ne dit qu'un devis existe : la configuration reste
        close, comme avant. `product_configurator_web_3d_sale` répond pour les lignes de devis.

        :returns: vrai si la configuration a été rouverte
        """
        return False

    def web_confirm(self):
        """Terminer la configuration : la variante naît, la session se ferme.

        ⚠️ **Une session confirmée ne se rouvre pas.** Elle a donné sa variante,
        et cette variante peut déjà être sur une commande : la changer ensuite
        serait pire qu'un refus (D-190, même raison que `set_value`).
        """
        self.ensure_one()
        missing = self._web_missing_attributes()
        if missing:
            # ⓘ Les NOMS, pas seulement le refus : la page doit pouvoir dire ce
            # qui manque, et l'utilisateur ne connaît pas nos identifiants.
            return {
                "error": "incomplete",
                "missing": missing.attribute_id.mapped("name"),
            }
        self.action_confirm()
        self._web_confirm_children()
        self._web_after_confirm()
        # ⓘ Close, la configuration n'a plus de conducteur : la main est rendue (D-371).
        self._release_hand()
        return self.web_state()

    def action_open_3d_page(self):
        """L'action qui EMMÈNE à la page 3D de cette configuration.

        Un seul endroit fabrique cette URL : la fiche produit et la ligne de
        devis y passent toutes les deux. Le jeton reste la seule identité, même
        au back-office — c'est ce qui permet d'ouvrir la même page, pour un
        interne comme pour un client (D-091).

        ⚠️ **UN DIALOGUE, PLUS UN ONGLET** — relevé de Gerry, 2026-09-07 :
        *« une nouvelle page s'ouvre au lieu d'un dialogue comme pour une ligne
        de devis »*. Un onglet fait perdre de vue ce qu'on faisait, et c'est
        justement ce qu'on ne veut pas d'un configurateur ouvert depuis un devis.
        Une action CLIENTE en `target: "new"` : Odoo l'enveloppe lui-même.

        ⓘ **L'état part AVEC l'action.** On vient de le calculer ; le redemander
        au montage coûterait un aller-retour pour la même réponse, et la page
        attendrait devant un écran vide (D-249).

        ⓘ Le JETON reste la seule identité, au back-office comme ailleurs
        (D-091) : c'est lui qui permet d'ouvrir la même configuration pour un
        interne et pour un client. L'URL publique existe toujours et se partage.

        ⓘ **`footer: False`** — relevé de Gerry, 2026-09-07 : *« le Ok et donc le
        footer est inutile car la croix est présente »*. Le pied qu'Odoo ajoute
        d'office ne porte qu'un bouton « Ok » qui ferme, exactement comme la
        croix du titre ; deux façons de faire le même geste, et l'une des deux
        ressemble à une validation qu'elle n'est pas. C'est `action_service`
        qui lit ce drapeau dans le contexte (`web/…/actions/action_service.js`).
        """
        self.ensure_one()
        self._ensure_access_token()
        return {
            "type": "ir.actions.client",
            "tag": "product_configurator_web_3d.configurator",
            "name": self.product_tmpl_id.display_name,
            "target": "new",
            "context": {"footer": False},
            "params": {
                "token": self.access_token,
                "state": self.web_state(),
            },
        }

    def _web_product_url(self):
        """L'adresse publique du produit — ou `None` s'il n'y a pas de site.

        ⚠️ **Le champ n'existe QUE si `website` est installé** (`website.published.mixin`),
        et ce module n'en dépend pas — il sert aussi un back-office sans boutique. On teste
        donc sa présence : absent, la page ne dessine pas de croix, plutôt que d'en dessiner
        une qui ne mène nulle part.
        """
        self.ensure_one()
        tmpl = self.product_tmpl_id
        return tmpl.website_url if "website_url" in tmpl._fields else None

    def web_state(self):
        """Tout ce qu'il faut à la page, en UNE réponse.

        ⚠️ Un seul aller-retour : la page s'ouvre sur un lien reçu par courriel,
        souvent sur un téléphone, et trois requêtes en série coûteraient plus que
        le rendu lui-même.
        """
        self.ensure_one()
        model3d = self._web_model3d()
        values = self._web_values()
        # ⓘ UNE SEULE FOIS : la définition est l'objet le plus cher de cette
        # réponse, et les matières s'y appuient pour savoir quelles pièces la
        # scène contient. La recalculer serait la payer deux fois par clic.
        definition = (model3d.to_definition(values, link_answers=self._web_link_answers())
                      if model3d else None)
        price = self.get_cfg_price(custom_vals=self._get_custom_vals_dict())
        separate = self.web_separate_lines(definition)
        # ⓘ UNE lecture des étapes pour les questions ET pour la liste qui suit : deux
        # lectures pourraient ne pas classer une question dans la même étape.
        layout = self._web_step_layout()
        step_views, question_views = self._web_views(layout[0], model3d)
        attributes = self._web_attribute_lines(layout=layout)
        # ⓘ D-387 — la vue d'un ATTRIBUT, que la page prend quand on ouvre ou répond à sa
        # question ; `None` : la caméra suit celle de l'étape, ou ne bouge pas.
        for question in attributes:
            question["camera"] = question_views.get(question["id"])
        return {
            "productName": self.product_tmpl_id.display_name,
            "state": self.state,
            "attributes": attributes,
            # ⓘ D-385 — les ÉTAPES visibles, dans l'ordre : les pastilles du haut du viewer.
            # Vide quand le produit n'en déclare aucune : la page reste une liste à plat.
            "steps": self._web_steps(layout[0], step_views),
            # ⚠️ AVEC les saisies (D-353) : une largeur tapée doit changer le prix
            # comme la même largeur choisie dans la liste.
            "price": price,
            # ⓘ D-368 — les lignes À PART (une pièce vendue à part) et le TOTAL que la page
            # affiche : le produit plus ses lignes. Le détail se lit au panier et au devis
            # (arbitrage de Gerry, 2026-09-28).
            "separateLines": separate,
            "total": price + sum(line["price"] * line["qty"] for line in separate),
            # ⚠️ Les réponses « sans variante », en `product.template.attribute.value` — à passer
            # au panier avec la ligne du produit. Sans elles, la boutique complète d'office
            # chaque question `no_variant` par sa PREMIÈRE valeur, et la ligne du JeNo affichait
            # « Bumper avant : Sans bumper » à côté de son bumper (mesuré). Depuis W-99, TOUTES
            # les réponses « sans variante » passent par là, vendues à part ou non.
            "noVariantPtavIds": self._web_no_variant_ptav_ids(),
            # La VARIANTE née de la confirmation, quand elle existe : c'est par elle
            # qu'une boutique met la configuration au panier.
            "productId": self.product_id.id or None,
            # ⚠️ **LA SORTIE — sans elle, la page atteinte par un LIEN est une porte fermée.**
            # La croix ne vivait que dans l'overlay de la fiche produit ; qui arrive par la
            # grille de la boutique, par un courriel ou par un clic donné avant la fin de la
            # préparation n'avait aucun moyen de revenir (relevé de Gerry, 2026-09-22).
            #
            # ⓘ Elle vient d'ICI et non du navigateur : revenir en arrière retomberait sur
            # `/configurator/start/<produit>`, qui crée une configuration NEUVE et renvoie
            # sur la page — une boucle. Et la route de la page ne résout pas le jeton, ce
            # que D-190 lui interdit précisément.
            "productUrl": self._web_product_url(),
            # Qui conduit (D-255). ⓘ Toujours présent, même libre : la page doit
            # pouvoir dire « personne » sans distinguer « absent » de « vide ».
            "hand": self._hand_state(),
            # L'attente a un visage : la photo du produit, puis la vue d'où elle
            # a été prise — la 3D se pose dessus au lieu d'apparaître ailleurs.
            "image": self._web_image(),
            "camera": self._web_camera(model3d),
            # L'AMBIANCE du produit — sous quel éclairage il se montre.
            "ambience": self._web_ambience(model3d),
            # Les MATIÈRES de toute la scène — la page ne peut pas les lire
            # elle-même : aucun de ces modèles n'est ouvert au public.
            "zones": self._web_zones(model3d, definition, values) if model3d else {},
            # ⓘ La définition porte la FORME, la portée porte les VALEURS : c'est
            # la séparation de D-163, et elle vaut ici comme dans l'éditeur.
            "definition": definition,
            "scope": model3d.get_attribute_scope(values) if model3d else {},
            # ⚠️ **LES PIÈCES DÉJÀ CUITES, et elles ne sont PAS dans la définition.**
            # Celle-ci est ce dont l'empreinte se calcule : y mettre le pointeur d'une
            # cuisson rendrait l'empreinte auto-référente — cuire changerait la définition,
            # donc l'empreinte, donc périmerait la cuisson qu'on vient d'écrire.
            #
            # ⓘ Servi dans le MÊME aller-retour que le reste : la page s'ouvre sur un lien
            # reçu par courriel, souvent sur un téléphone, et c'est la règle de cette
            # méthode.
            "baked": model3d.baked_parts(values) if model3d else {},
            # ⚠️ **LES FICHIERS IMPORTÉS, avec leur URL à jeton** — hors de la définition
            # pour la même raison que la cuisson. Sans eux, toute pièce de fichier était un
            # volume VIDE sur la page : les inserts du JeNo manquaient (Gerry, 2026-09-24).
            "imported": model3d.imported_files(values) if model3d else {},
            # Les PLACEMENTS que le client peut régler — et eux seuls (D-332, D-333).
            "placements": self._web_placements(model3d, definition, values) if model3d else {},
        }
