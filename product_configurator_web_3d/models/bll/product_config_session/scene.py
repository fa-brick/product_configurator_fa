"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
from odoo import models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

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

        ⚠️ **Le reflet au sol et la photo d'environnement passent tels quels**, même sur un
        téléphone où ils coûtent cher (un rendu de la scène par image ; deux à vingt
        mégaoctets) : les filtrer ici les ferait disparaître chez le client alors que
        l'auteur de la scène les a voulus. L'éditeur AVERTIT à la place, dans son onglet Rendu.

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
                    # ⚠️ `isdigit` : la clé du TEXTE d'une réponse (`__attribute_text_<id>`, W-136)
                    #    partage le préfixe, et `int()` y lèverait.
                    answers = {
                        int(key[len(marker):]): value
                        for key, value in answers_by_node[child["id"]].items()
                        if key.startswith(marker) and key[len(marker):].isdigit()
                        and int(key[len(marker):]) in drivers
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
        (D-333).

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
            # ⚠️ **LES BORNES** : le viewer ne borne que ce qu'on lui donne — sans elles, les
            # limites de la vue sont ignorées sur la page (D-389).
            # ⓘ Les distances partent en FACTEURS, telles qu'en base (`distanceIn`) : le rayon
            # qui les convertit en millimètres dépend de la scène et du canevas, que seul le
            # viewer connaît (D-389).
            "limits": {
                "azimuthMin": camera.azimuth_min,
                "azimuthMax": camera.azimuth_max,
                "inclinationMin": camera.inclination_min,
                "inclinationMax": camera.inclination_max,
                "distanceMin": camera.distance_min,
                "distanceMax": camera.distance_max,
                "distanceIn": "factor",
            },
            # ⚠️ LA CIBLE fait partie de la vue (D-116) : sans elle, la page pose la vue
            # sans centre, et une pièce isolée puis quittée garde son centre — le retour
            # doit rejouer la vue du produit avec sa cible (D-333).
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
        rend le pictogramme d'Odoo, et l'attente montre un appareil photo barré
        au lieu de la pièce. C'est le même mur
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

    def _web_fonts(self, definition):
        """Les polices que la définition CITE — `{id: {name, url}}` (W-136, D-499).

        ⓘ `engine_fonts` est en `sudo` : le visiteur n'a aucun droit sur les polices.
        ⚠️ L'URL porte son jeton : `/web/content/<id>` nu répond 404 à un visiteur ([[L-599]]).
        """
        Font = self.env["product.model3d.font"]
        return Font.engine_fonts(Font.cited_in(definition))
