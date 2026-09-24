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

from odoo import api, fields, models

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

    def _web_attribute_lines(self):
        """Les questions du produit, avec ce qui reste disponible.

        ⚠️ La disponibilité se demande à `values_available` — celle qui sert déjà
        à l'assistant — et non à une règle réécrite ici. Deux évaluateurs d'une
        même restriction finiraient par diverger, et c'est le client qui verrait
        la différence.
        """
        self.ensure_one()
        chosen = self.value_ids.ids
        out = []
        for line in self.product_tmpl_id.attribute_line_ids.sorted():
            values = line._configurator_value_ids()
            available = set(
                self.values_available(
                    check_val_ids=values.ids,
                    value_ids=chosen,
                    product_template_attribute_line_id=line.id,
                )
            )
            out.append({
                "id": line.attribute_id.id,
                "name": line.attribute_id.name,
                "required": bool(line.required),
                "multi": bool(line.multi),
                # ⚠️ **LA FORME QU'ON A DONNÉE À LA QUESTION.** Réglée en
                # back-office depuis toujours, elle n'était pas servie : la page
                # rendait un bouton pour tout, quel que soit le type. Cinq
                # formes chez Odoo, plus la « carte » — une vignette et son
                # libellé — qui manquait pour une valeur désignant un produit.
                "displayType": line.attribute_id.display_type,
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
                        # ⚠️ La valeur INDISPONIBLE est rendue quand même, marquée.
                        # C'est D-168 et D-178 : on la grise, et un appui dira
                        # pourquoi. La retirer ici ôterait à la page le moyen de
                        # le faire.
                        "available": value.id in available,
                        "chosen": value.id in chosen,
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

        materials = self._web_materials(needed)
        for zones in zones_by_piece.values():
            for zone in zones:
                zone["material"] = materials.get(zone["renderMaterialId"]) or None
        return {
            "zonesByPiece": zones_by_piece,
            # Par ID : la page y puise sans que la même fiche voyage deux fois.
            "materials": materials,
        }

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
            # ⓘ LA CIBLE fait partie de la vue (D-116). Sans elle, la page posait la
            # pose sans centre — et une pièce isolée puis quittée gardait le centre de
            # la pièce. Gerry (2026-09-23) : « lorsque l'on quitte, il faut revenir à
            # la vue caméra en cours, qui donnera la target ».
            "target": self._web_camera_target(camera),
        }

    def _web_camera_target(self, camera):
        """La cible d'une vue, telle que le viewer la résout : un NŒUD `c<linkId>`, la
        MATIÈRE (`root`) ou l'ORIGINE. Miroir de `_resolveCameraTarget` de l'éditeur —
        `root` et `origin` ne sont pas la même chose (D-116)."""
        if camera.target_kind == "piece" and camera.target_link_id:
            # ⚠️ L'identité du NŒUD que le lien pose, lue dans la définition (D-349) : un
            # lien imbriqué s'appelle `c10/c11`, et `c<lien>` ne le trouverait pas.
            return {"nodeId": self._web_node_id_of_link(camera.target_link_id)}
        if camera.target_kind == "root":
            return {"root": True}
        return {"origin": True}

    def _web_node_id_of_link(self, link):
        """Le nœud de la PREMIÈRE pose d'un lien dans la définition — `c<lien>` à défaut,
        l'identité d'un enfant direct. Une caméra vise une place, pas une pose."""
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
        out = {}

        def walk(node):
            for child in node.get("children") or []:
                editable = child.get("editableAttributeIds") or []
                link_id = child.get("linkId")
                if editable and link_id:
                    out[child["id"]] = self._web_placement(
                        Model3d, Session, child, link_id, editable,
                        child_values.get(str(link_id)) or child_values.get(link_id) or {},
                        variants)
                walk(child)

        walk(definition)
        return out

    def _web_placement(self, Model3d, Session, node, link_id, editable, answers, variants):
        piece = Model3d.browse(node.get("model3dId")).exists()
        link = self.env["product.model3d.component"].sudo().browse(link_id).exists()
        tmpl = piece.product_tmpl_id
        variant = link._swapped_variant(variants) if link else None
        by_attr = {
            ptav.attribute_id.id: ptav.product_attribute_value_id.id
            for ptav in (variant.product_template_attribute_value_ids if variant else [])
        }
        # Ce que le client a choisi, sinon ce que la VARIANTE désignée porte, sinon le
        # défaut de la ligne — la même pile que `_child_node`, lue pour cocher.
        chosen_ids = []
        for line in tmpl.attribute_line_ids:
            attr_id = line.attribute_id.id
            picked = (answers.get(str(attr_id)) or answers.get(attr_id)
                      or by_attr.get(attr_id)
                      or (line.default_val.id if "default_val" in line._fields and line.default_val else None))
            if picked:
                chosen_ids.append(int(picked))
        questions = []
        for line in tmpl.attribute_line_ids.sorted():
            if line.attribute_id.id not in editable:
                continue
            values = line._configurator_value_ids()
            try:
                available = set(Session.values_available(
                    check_val_ids=values.ids, value_ids=list(chosen_ids), custom_vals={},
                    product_tmpl_id=tmpl.id, product_template_attribute_line_id=line.id))
            except Exception:  # noqa: BLE001 — un évaluateur qui tombe ne doit pas cacher la question
                _logger.warning("placement %s: availability could not be evaluated", link_id,
                                exc_info=True)
                available = set(values.ids)
            questions.append({
                "id": line.attribute_id.id,
                "name": line.attribute_id.name,
                "required": bool(line.required),
                "multi": bool(line.multi),
                "displayType": line.attribute_id.display_type,
                "values": [{
                    "id": value.id,
                    "name": value.display_value or value.name,
                    "available": value.id in available,
                    "chosen": value.id in chosen_ids,
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
        # de lui-même — la même diffusion, l'état complet.
        self._notify_configuration_changed()
        return self.web_state()

    def _web_confirm_children(self):
        """La VARIANTE de chaque placement RÉPONDU naît à la confirmation — D-332.

        Le même geste que pour la racine (D-190) : un gabarit, des réponses, une variante.
        ⚠️ Retenue sur la session (`child_variants`), SANS effet commercial dans ce lot :
        la commande, la nomenclature et le prix des composants sont 7-9/7-10.

        ⚠️ Une variante qui ne peut pas naître (réponse d'auteur par FORMULE, que le
        serveur ne résout pas ; gabarit sans variantes) est consignée, jamais bloquante :
        la confirmation de la racine ne dépend pas d'un enfant.
        """
        self.ensure_one()
        model3d = self._web_model3d()
        if not model3d:
            return {}
        values = self._web_values()
        definition = model3d.to_definition(values, link_answers=self._web_link_answers())
        placements = self._web_placements(model3d, definition, values)
        born = {}
        for placement in placements.values():
            link_id = placement["linkId"]
            answered = (self.child_values or {}).get(str(link_id))
            if not answered:
                continue
            child_model_id = self._web_placement_model_id(definition, placement["nodeId"])
            tmpl = self.env["product.model3d"].sudo().browse(child_model_id).product_tmpl_id
            if not tmpl:
                continue
            value_ids = []
            for question in placement["questions"]:
                value_ids += [v["id"] for v in question["values"] if v["chosen"]]
            # Les questions FIXÉES par l'auteur (hors `questions`) : leur valeur résolue
            # entre aussi, quand c'est une valeur et non une formule.
            node_overrides = self._web_placement_overrides(definition, placement["nodeId"])
            for attr_key, binding in node_overrides.items():
                if not isinstance(binding, dict) or "value" not in binding:
                    continue
                attribute = self.env["product.attribute"].browse(int(attr_key)).exists()
                if not attribute or attribute.id in {q["id"] for q in placement["questions"]}:
                    continue
                value = attribute.resolve_answer(binding["value"])
                if value:
                    value_ids.append(value.id)
            # ⓘ **Par le cœur d'Odoo, pas par une session de l'enfant.** La recherche de
            # variante d'OCA (`search_variant`) ne retrouve pas celles qu'Odoo engendre
            # lui-même à la création des lignes d'attribut : elle en CRÉAIT une seconde, et
            # la contrainte d'unicité de la combinaison tombait au vidage — mesuré. Le cœur
            # sait retrouver une combinaison (`_get_variant_for_combination`) et la créer
            # pour un attribut dynamique (`_create_product_variant`).
            #
            # ⚠️ **SOUS UN POINT DE SAUVEGARDE, et VIDÉ avant d'être retenu** : une erreur
            # SQL attrapée sans point de sauvegarde laisse la transaction en échec, et un
            # identifiant retenu avant le vidage désigne une ligne qu'un repli a effacée.
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
                born[str(link_id)] = variant.id
            except Exception:  # noqa: BLE001
                _logger.warning("placement %s: the child variant could not be born", link_id,
                                exc_info=True)
        if born:
            self.write({"child_variants": born})
        return born

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
        return {
            value.attribute_id.id: (
                value.name if value.attribute_id.is_numeric() else value.id
            )
            for value in self.value_ids
        }

    def _web_missing_attributes(self):
        """Les questions OBLIGATOIRES restées sans réponse.

        ⚠️ **La visibilité passe AVANT l'exigence** — c'est la règle de D-086 :
        un attribut masqué par une condition cesse d'être obligatoire. Sans
        cela, une question que le client ne voit pas l'empêcherait de terminer,
        et rien à l'écran ne dirait pourquoi.

        ⓘ On ne s'appuie PAS sur `check_and_open_incomplete_step` : elle ne
        regarde que les ÉTAPES (`get_open_step_lines`), donc un produit qui n'en
        déclare aucune passerait sans contrôle. La page ne montre pas encore les
        étapes ; elle doit pourtant refuser une configuration incomplète.
        """
        self.ensure_one()
        chosen = self.value_ids
        missing = self.env["product.template.attribute.line"]
        for line in self.product_tmpl_id.attribute_line_ids:
            if not line.required or not line._is_visible(value_ids=chosen):
                continue
            if not (line._configurator_value_ids() & chosen):
                missing |= line
        return missing

    def _notify_configuration_changed(self):
        """Diffuser le nouvel état à tous ceux qui regardent — D-253.

        ⓘ On envoie **l'état complet**, pas un delta : c'est exactement ce que
        `/configurator/state` rend, donc la page l'applique avec le code qu'elle
        a déjà — et `toViewModel(next, previous)` garde la définition quand la
        recette n'a pas changé, si bien qu'un spectateur ne reconstruit pas sa
        géométrie pour un changement de couleur (D-191).

        ⚠️ Le prix de cette simplicité est la TAILLE du message : la définition
        3D voyage à chaque clic, pour chaque spectateur. Acceptable tant qu'on
        regarde à deux ou trois ; à revoir si une présentation se joue devant
        une salle.
        """
        self.ensure_one()
        self._bus_send("configurator_state", self.web_state())
        return super()._notify_configuration_changed()

    def _web_after_confirm(self):
        """Ce qui suit la confirmation, là où la configuration ATTERRIT.

        Vide ici, et c'est voulu : le cœur de l'interface ne sait pas ce qu'est
        un devis. `product_configurator_web_3d_sale` s'y branche pour écrire la
        ligne. Un autre atterrissage (un panier, une demande) s'y brancherait
        pareil, sans toucher à cette classe.
        """
        return True

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
        return {
            "productName": self.product_tmpl_id.display_name,
            "state": self.state,
            "attributes": self._web_attribute_lines(),
            "price": self.get_cfg_price(),
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
            # Les PLACEMENTS que le client peut régler — et eux seuls (D-332, D-333).
            "placements": self._web_placements(model3d, definition, values) if model3d else {},
        }
