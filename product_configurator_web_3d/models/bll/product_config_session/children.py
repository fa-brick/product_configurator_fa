"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

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
        pas, et le survol ne le nomme pas (D-333).

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
            entry = resolved.get(marker + str(attribute.id))
            value_id = self._web_value_of_entry(line, entry)
            if str(attribute.id) in formulas and not value_id:
                # ⓘ Une FORMULE du lien est résolue par le moteur (`_node_answers`, P-a de
                # W-111). Son résultat hors des valeurs offertes devient une VALEUR, comme une
                # saisie (D-353) — une largeur calculée de 2 880 n'est dans aucune liste.
                # ⚠️ Sinon (Node absent, attribut sans variante) : la réponse d'en dessous, dite.
                value = (line.resolve_custom_value(entry)
                         if entry is not None and attribute._resolves_to_values() else None)
                if value:
                    value_id = value.id
                else:
                    _logger.info("placement %s: “%s” is computed by a formula that gave no "
                                 "value (%r); its variant takes the answer below it",
                                 link_id, attribute.display_name, entry)
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
