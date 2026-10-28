"""Ce qu'exécute `product.config.session` (BLL, D-541).

L'état d'une session, tel que la PAGE PUBLIQUE le lit — D-091, lot 6.

Ce module ne sait rien du HTTP : il rend un dictionnaire. Le contrôleur ne fait
que l'appeler, ce qui rend l'essentiel éprouvable **sans serveur** — et c'est ce
qui manquait au lot 6, dont le blocage n° 4 était l'absence de tout harnais.

⚠️ **Ce que la page reçoit, et ce qu'elle ne reçoit PAS.** Elle reçoit les
questions, leurs réponses possibles, le prix et la définition 3D. Elle ne reçoit
ni identifiant interne de session, ni jeton d'une autre, ni rien qui permette
d'énumérer : le jeton entre, il ne ressort pas.
"""
from collections import Counter
from odoo import api, models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

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
        visible** (D-385). Sans étape visible, elles
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

        ⓘ Une vue est celle qu'on a posée, sinon RIEN : la caméra ne bouge pas (D-163).
        La page résout ensuite « l'attribut, sinon son étape » au moment où l'on ouvre
        ou répond à une question.

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
                        # pour la même largeur.
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
                        # `_web_value_has_image` dit si l'image EXISTE — une vignette
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

        ⓘ **Seule la FEUILLE se nomme** — sauf quand deux feuilles
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
        lot C qui en ajoutait une a été abandonné pour cette raison (D-353).

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
            "maxLength": spec.get("max_length") or None,
        }

    def _web_offered_values(self, line):
        """Les valeurs qu'une question OFFRE — sans la valeur « Custom » d'OCA.

        ⚠️ `_configurator_value_ids()` ajoute cette valeur spéciale à toute ligne qui
        autorise l'ajout : c'est le jeton par lequel l'ancien assistant ouvrait son champ.
        ⚠️ Elle appartient à un AUTRE attribut : rendue par la page, elle devient un
        bouton « Custom » sans issue sur chaque question qui autorise l'ajout (D-353).
        Ici, la saisie a son propre champ.
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

        ⓘ Le contrôle ne passe PAS par les seules ÉTAPES (`get_open_step_lines`) : un
        produit qui n'en déclare aucune passerait sans contrôle.
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
        pricelist, day = self._web_pricing()
        price = self.get_cfg_price(
            custom_vals=self._get_custom_vals_dict(), pricelist=pricelist, date=day)
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
            # affiche : le produit plus ses lignes. Le détail des lignes à part se lit au
            # panier et au devis (D-368).
            "separateLines": separate,
            "total": price + sum(line["price"] * line["qty"] for line in separate),
            # ⓘ D-537 — une cote hors de la grille : le message, et le panier fermé.
            "outOfGrid": self._out_of_grid_message(date=day),
            # ⚠️ Les réponses « sans variante », en `product.template.attribute.value` — à passer
            # au panier avec la ligne du produit. Sans elles, la boutique complète d'office
            # chaque question `no_variant` par sa PREMIÈRE valeur, et la ligne du JeNo affichait
            # « Bumper avant : Sans bumper » à côté de son bumper (mesuré). Depuis W-99, TOUTES
            # les réponses « sans variante » passent par là, vendues à part ou non.
            "noVariantPtavIds": self._web_no_variant_ptav_ids(),
            # La VARIANTE née de la confirmation, quand elle existe : c'est par elle
            # qu'une boutique met la configuration au panier.
            "productId": self.product_id.id or None,
            # ⚠️ **LA SORTIE — sans elle, la page atteinte par un LIEN est une porte fermée** :
            # la croix de l'overlay de la fiche produit n'existe pas pour qui arrive par la
            # grille de la boutique, par un courriel ou avant la fin de la préparation.
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
            # volume VIDE sur la page : les inserts du JeNo manquaient (D-487).
            "imported": model3d.imported_files(values) if model3d else {},
            # ⚠️ **LES POLICES de la forme Texte**, avec leur URL à jeton — hors de la
            # définition pour la même raison (W-136). Sans elles, la plaque s'affiche sans
            # son numéro.
            "fonts": self._web_fonts(definition) if model3d else {},
            # Les PLACEMENTS que le client peut régler — et eux seuls (D-332, D-333).
            "placements": self._web_placements(model3d, definition, values) if model3d else {},
        }
