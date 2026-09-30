/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
/**
 * configurator_state.js — Ce que la page fait de la réponse du serveur (lot 6).
 *
 * **Pur, et c'est délibéré.** Le fork n'avait aucun harnais de test JS — c'était le
 * blocage n° 4 du lot 6. Plutôt que d'écrire une page qu'on ne pourrait pas éprouver, la
 * logique vit ici : ce qu'on affiche, ce qu'on refuse de cliquer, ce qu'on renvoie, et
 * **quand la 3D doit se reconstruire**. Le composant, lui, ne fera que monter et brancher.
 *
 * ─ La règle qui coûte le plus cher si on l'oublie ────────────────────────────
 *
 * ⚠️ **Répondre à une question ne change pas la FORME du produit, seulement ses valeurs.**
 * La définition 3D — la recette — ne bouge qu'à une permutation de pièce (D-164) ; le reste
 * du temps, seule la **portée** change (D-163). Rendre une définition NEUVE à chaque clic
 * ferait reconstruire la géométrie entière pour un changement de couleur : le viewer décide
 * de reconstruire sur une comparaison de RÉFÉRENCE, et une référence neuve suffit à tout
 * refaire. On garde donc l'ancienne quand elle n'a pas changé.
 */

/** Les tailles d'une carte ou d'une grande pastille (`answer_size`, D-382). */
export const ANSWER_SIZES = ["small", "medium", "large"];

/** Les formes qui montrent une IMAGE, et celles qu'une ligne résumé remplace (D-382). */
const IMAGE_FORMS = ["card", "swatch"];
const SUMMARY_FORMS = ["card", "swatch", "radio", "pills", "select"];

/**
 * La disposition EFFECTIVE d'une question — D-382.
 *
 * ⓘ Le miroir de `_web_answer_layout` côté serveur, qui la sert déjà ramenée : ce calcul
 * couvre le serveur qui ne la sert pas encore, et toute combinaison sans effet. Une
 * disposition inconnue ou absente est `inline`, l'affichage d'avant ce réglage.
 */
export function answerLayoutOf(line) {
    const layout = line.answerLayout;
    const form = line.displayType || "radio";
    if ((layout === "scroll" || layout === "line") && IMAGE_FORMS.includes(form)) return layout;
    if (layout === "summary" && SUMMARY_FORMS.includes(form)) return layout;
    return "inline";
}

/**
 * Le défilement qui montre un élément EN ENTIER dans une rangée — ou `null` s'il l'est
 * déjà. Positions en pixels, relatives au début du contenu de la rangée.
 *
 * ⓘ Le moins possible : un élément coupé à gauche vient se caler au bord gauche, un
 * élément coupé à droite au bord droit. ⚠️ On ne touche pas à la rangée quand il est
 * visible — la page se rend à chaque réponse, et ramener la rangée à chaque rendu
 * reprendrait la main à celui qui fait défiler.
 */
export function revealScrollLeft(scrollLeft, viewWidth, itemLeft, itemWidth) {
    if (itemLeft < scrollLeft) return itemLeft;
    if (itemLeft + itemWidth > scrollLeft + viewWidth) {
        return Math.max(0, itemLeft + itemWidth - viewWidth);
    }
    return null;
}

/**
 * Les bords qu'une rangée a atteints — ce qui cache sa flèche devenue inutile (D-382).
 * ⓘ Au pixel près : un défilement fractionnaire s'arrête souvent à 0,5 px du bord.
 */
export function rowEdges(scrollLeft, viewWidth, scrollWidth) {
    return {
        start: scrollLeft <= 1,
        end: scrollLeft + viewWidth >= scrollWidth - 1,
    };
}

// ── LA LIGNE, LE RÉSUMÉ, LE PANNEAU (D-382, lot 3) ──────────────────────────

/**
 * La largeur MINIMALE d'une réponse dans sa grille, par forme et par taille — les valeurs
 * de `configurator_page.scss` (`minmax(…)`), que `answer_size.test.js` tient ensemble.
 * ⓘ Pour la grande pastille, c'est la CASE de la grille, pas le disque.
 */
export const ANSWER_MIN_WIDTH = {
    card: { small: 64, medium: 88, large: 140 },
    swatch: { small: 64, medium: 84, large: 108 },
};
/** L'écart entre deux réponses, et la marge intérieure de la grille des pastilles. */
export const ANSWER_GAP = 8;
const SWATCH_GRID_PADDING = 8;

/** Les formes à image — celles qui ont une grille, et une bascule de vue au panneau. */
export function isImageForm(question) {
    return IMAGE_FORMS.includes(question.displayType);
}

/**
 * Ce qu'une rangée `line` montre : autant de réponses qu'il en tient sur UNE ligne, la
 * dernière case cédée à « +N » quand toutes n'y tiennent pas — D-382.
 *
 * ⚠️ **Le choix est TOUJOURS dans la rangée** : s'il tombe au-delà, il prend la dernière
 * place visible. Sinon le client ne voit pas ce qu'il a choisi (analyse, §3).
 *
 * ⓘ Sans largeur mesurée (`width` nul, avant le premier `ResizeObserver`), tout est montré :
 * la grille d'avant, plutôt qu'une rangée tronquée au hasard.
 *
 * @returns {{values: object[], more: number}}
 */
export function lineOf(values, width, form, size) {
    if (!width || !ANSWER_MIN_WIDTH[form]) return { values, more: 0 };
    const min = ANSWER_MIN_WIDTH[form][size] || ANSWER_MIN_WIDTH[form].medium;
    const inner = form === "swatch" ? width - SWATCH_GRID_PADDING : width;
    const capacity = Math.max(1, Math.floor((inner + ANSWER_GAP) / (min + ANSWER_GAP)));
    if (values.length <= capacity) return { values, more: 0 };
    const slots = Math.max(1, capacity - 1);
    let shown = values.slice(0, slots);
    const chosen = values.find((value) => value.chosen);
    if (chosen && !shown.includes(chosen)) shown = [...shown.slice(0, slots - 1), chosen];
    return { values: shown, more: values.length - shown.length };
}

/** Un texte ramené à ce qu'une recherche compare : sans accents, sans casse. */
export function searchable(text) {
    return String(text ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

/** Les réponses dont le NOM contient la recherche — « creme » trouve « Crème ». */
export function filterAnswers(values, query) {
    const wanted = searchable(query);
    return wanted ? values.filter((value) => searchable(value.name).includes(wanted)) : values;
}

/**
 * La vue d'ouverture du panneau. Une forme sans image n'a que la liste ; une forme à image
 * s'ouvre en grille, grande si l'attribut le dit, petite sinon — le panneau sert à PARCOURIR,
 * la moyenne y cède à la petite (plan, lot 3).
 */
export function panelViewOf(question) {
    if (!isImageForm(question)) return "list";
    return question.answerSize === "large" ? "large" : "small";
}

/** La réponse choisie d'une question à choix simple — `null` s'il n'y en a pas. */
export function pickedAnswer(question) {
    return question.values.find((value) => value.chosen) || null;
}

/** La pastille des réponses SANS catégorie — « Autres », toujours la dernière. */
export const OTHER_CATEGORY = "__other__";

/**
 * Les pastilles de catégories d'un panneau — D-382 (Gerry : « des pastilles horizontales
 * sous la recherche qui filtrent », « autre et tout »).
 *
 * « Tout » d'abord (clé `null`), les catégories dans l'ordre servi, « Autres » en dernier
 * s'il reste des réponses sans catégorie. ⓘ **Aucune pastille sous deux groupes** : une
 * seule catégorie ne filtrerait rien.
 */
export function panelChips(question, allLabel, otherLabel) {
    const categories = question.categories || [];
    const hasOther = question.values.some((value) => !(value.categoryKeys || []).length);
    if (categories.length + (hasOther ? 1 : 0) < 2) return [];
    return [
        { key: null, label: allLabel },
        ...categories.map((category) => ({ key: category.key, label: category.name })),
        ...(hasOther ? [{ key: OTHER_CATEGORY, label: otherLabel }] : []),
    ];
}

/** Les réponses d'une pastille — filtre EXACT, sans les sous-catégories (Gerry). */
export function filterByCategory(values, key) {
    if (!key) return values;
    if (key === OTHER_CATEGORY) return values.filter((value) => !(value.categoryKeys || []).length);
    return values.filter((value) => (value.categoryKeys || []).includes(key));
}

// ── LES ÉTAPES — D-385 ───────────────────────────────────────────────────────────
//
// ⚠️ **UNE ÉTAPE EST UN MARQUEUR, PAS UN CONTENANT** (D-202) : le serveur range chaque
// question dans la sienne (`stepId`) et ne sert que les étapes VISIBLES. La page n'a donc
// rien à déduire de l'ordre : elle filtre, et grise.
//
// Arbitrage de Gerry (2026-09-30) : les étapes s'affichent en pastilles en haut du
// viewer ; l'étape suivante reste GRISÉE tant qu'une question obligatoire manque ; un
// clic sur une pastille grisée DIT ce qui manque et y MÈNE.

/** Une étape telle que la page la rend — sa vue, ou `null` : la caméra ne bouge pas. */
function toStep(raw) {
    return { id: raw.id, name: raw.name || "", camera: raw.camera || null };
}

/** L'étape affichée : celle qu'on a choisie si elle est encore servie, sinon la première. */
export function activeStepId(steps, wanted) {
    if (!steps.length) return null;
    return steps.some((step) => step.id === wanted) ? wanted : steps[0].id;
}

/**
 * La vue à montrer quand on travaille une question : la sienne, sinon celle de son étape,
 * sinon `null` — la caméra ne bouge pas (D-163, D-387).
 */
export function questionView(question, steps) {
    if (!question) return null;
    if (question.camera) return question.camera;
    return steps.find((step) => step.id === question.stepId)?.camera || null;
}

/** Les questions de l'étape affichée — toutes quand le produit n'a pas d'étape. */
export function stepQuestions(questions, steps, activeId) {
    if (!steps.length) return questions;
    return questions.filter((question) => question.stepId === activeId);
}

/**
 * Les questions obligatoires qui manquent AVANT une étape — dans l'ordre des étapes, puis
 * des questions. `targetId` nul : toutes celles qui manquent (la confirmation).
 *
 * ⓘ C'est ce qui bloque l'accès à `targetId` : une étape se mérite par TOUTES celles qui
 * la précèdent, pas seulement par la précédente — sans quoi on sauterait une étape
 * incomplète en passant par la suivante.
 */
export function missingBefore(steps, questions, targetId = null) {
    const missing = questions.filter((question) => question.missing);
    if (!steps.length) return targetId === null ? missing : [];
    const order = new Map(steps.map((step, index) => [step.id, index]));
    const rank = (question) => order.get(question.stepId) ?? steps.length;
    // ⓘ `sort` est stable : l'ordre des questions tient à l'intérieur d'une étape.
    const sorted = [...missing].sort((a, b) => rank(a) - rank(b));
    if (targetId === null) return sorted;
    const limit = order.get(targetId) ?? 0;
    return sorted.filter((question) => rank(question) < limit);
}

/**
 * Les pastilles d'étape : `{id, name, active, locked}`.
 *
 * ⓘ `locked` : une question obligatoire manque dans une étape qui PRÉCÈDE. L'étape
 * affichée n'est jamais verrouillée — on doit pouvoir y répondre.
 */
export function stepChips(steps, questions, activeId) {
    return steps.map((step) => ({
        id: step.id,
        name: step.name,
        active: step.id === activeId,
        locked: step.id !== activeId && missingBefore(steps, questions, step.id).length > 0,
    }));
}

/** Une question, telle que la page la rend — de la racine ou d'un placement. */
function toQuestion(line) {
    return {
        id: line.id,
        name: line.name,
        required: !!line.required,
        multi: !!line.multi,
        // ⓘ Le repli est `radio`, comme chez Odoo : une question sans forme
        // déclarée reste une question, elle ne disparaît pas.
        displayType: line.displayType || "radio",
        // ⓘ La marque du choix d'une grande pastille — la coche si rien n'est dit.
        swatchMark: line.swatchMark === "ring" ? "ring" : "check",
        // ⓘ La taille d'une carte ou d'une grande pastille (D-382) — `medium`, l'affichage
        // d'avant ce réglage, pour toute valeur inconnue ou absente (un serveur qui ne la
        // sert pas encore).
        answerSize: ANSWER_SIZES.includes(line.answerSize) ? line.answerSize : "medium",
        // ⓘ Sa disposition (D-382) : `inline` pour toute combinaison sans effet.
        answerLayout: answerLayoutOf(line),
        // ⓘ Les catégories présentes parmi ses réponses, dans l'ordre d'affichage (D-382).
        categories: Array.isArray(line.categories) ? line.categories : [],
        values: (line.values || []).map(toValue),
        // ⓘ **LA SAISIE LIBRE** (D-353) : la forme du champ, ou `null` quand la question
        // se répond par sa liste. C'est ELLE qui décide du champ, avant `displayType` —
        // aucune forme d'affichage nouvelle (lot C abandonné le 2026-09-08).
        free: line.free ? toFreeField(line.free) : null,
        // Ce que le client a TAPÉ, tel que le serveur l'a rangé — `null` s'il a choisi.
        customValue: line.customValue ?? null,
        // ⓘ D-385 — l'étape qui porte la question (`null` hors étape), et si une réponse
        // OBLIGATOIRE y manque : le serveur en décide, avec l'évaluateur de la confirmation.
        stepId: line.stepId ?? null,
        missing: !!line.missing,
        // ⓘ D-387 — la vue 3D de l'attribut, `null` s'il n'en déclare pas.
        camera: line.camera || null,
    };
}

/** La forme d'un champ de saisie — `null` partout où rien n'est déclaré. */
function toFreeField(raw) {
    return {
        numeric: !!raw.numeric,
        unit: raw.unit || "",
        // ⚠️ `?? null` et non `|| null` : une borne à ZÉRO est une vraie borne.
        min: raw.min ?? null,
        max: raw.max ?? null,
        step: raw.step || null,
        maxLength: raw.maxLength || null,
        regexp: raw.regexp || null,
    };
}

/**
 * Ce que le champ de saisie AFFICHE : la saisie, sinon la valeur choisie — ou rien.
 *
 * ⓘ Pour une valeur choisie, la forme RANGÉE (`raw`, « 150 ») et non le libellé
 * (« 150 mm ») : le champ se retape, et l'unité y reviendrait à chaque correction.
 * L'unité s'écrit à côté du champ.
 *
 * @param {object} question
 * @param {string} [decimalPoint] le séparateur décimal du visiteur — « , » en français
 */
export function freeText(question, decimalPoint = ".") {
    if (!question) return "";
    const chosen = (question.values || []).find((v) => v.chosen);
    const text = question.customValue ?? chosen?.raw ?? chosen?.name ?? "";
    const shown = String(text);
    // ⓘ Le serveur range le nombre avec un POINT (D-160) ; on le rend dans la langue du
    // visiteur, qui a pu taper « 2,5 » et ne doit pas voir sa virgule disparaître.
    return question.free?.numeric && decimalPoint !== "."
        ? shown.replace(".", decimalPoint)
        : shown;
}

/**
 * La contrainte, sous le champ — « 600 → 1200 mm », « 20 characters max ».
 *
 * La même règle que l'éditeur (`_boundsLabel`) : rien quand rien n'est borné, et une borne
 * à zéro est une borne.
 */
export function boundsLabel(question) {
    const free = question?.free;
    if (!free) return "";
    if (!free.numeric) {
        return free.maxLength ? _t("%s characters max", free.maxLength) : "";
    }
    const low = free.min;
    const high = free.max;
    if (low === null && high === null) return "";
    const unit = free.unit ? ` ${free.unit}` : "";
    if (low !== null && high !== null) return `${low} → ${high}${unit}`;
    return low !== null ? `≥ ${low}${unit}` : `≤ ${high}${unit}`;
}

/**
 * Les SUGGESTIONS d'un champ de saisie : les valeurs que la question offre déjà.
 *
 * ⓘ Choisir une suggestion est un CLIC sur la valeur — elle repart par son identifiant,
 * jamais par son libellé. Une valeur éteinte n'est pas proposée : la suggérer inviterait
 * à un choix que le serveur refuserait.
 */
export function freeSuggestions(question, request = "") {
    const needle = String(request || "").trim().toLowerCase();
    return (question?.values || [])
        .filter((v) => v.available)
        .filter((v) => !needle || String(v.name).toLowerCase().includes(needle))
        .map((v) => ({ label: v.name, value: v.id }));
}

/**
 * Ce qu'il faut envoyer pour une SAISIE — ou `null` si rien ne doit partir.
 *
 * ⚠️ **Une saisie identique à la réponse en cours ne part pas** : quitter un champ qu'on
 * n'a pas modifié ferait reconstruire la 3D et la diffuser à tous ceux qui regardent,
 * pour rien (D-253).
 *
 * ⓘ Une saisie VIDE part : c'est le geste qui efface la réponse tapée.
 *
 * @param {object} model
 * @param {object} question
 * @param {string} raw ce que le champ contient
 * @param {object} [placement] le placement sélectionné, pour une question d'enfant
 */
export function customAnswerFor(model, question, raw, placement = null, decimalPoint = ".") {
    if (!model || model.error || model.closed || !question?.free) return null;
    const text = String(raw ?? "").trim();
    if (text === freeText(question, decimalPoint).trim()) return null;
    const payload = { attribute_id: question.id, custom_value: text };
    if (placement) payload.link_id = placement.linkId;
    return payload;
}

/** `{ nodeId → placement }` — un placement porte son lien, son nom et ses questions. */
function toPlacements(raw) {
    const out = {};
    for (const [nodeId, placement] of Object.entries(raw || {})) {
        out[nodeId] = {
            nodeId,
            linkId: placement.linkId ?? null,
            label: placement.label || "",
            questions: (placement.questions || []).map(toQuestion),
        };
    }
    return out;
}

/**
 * Le PLACEMENT réglable d'une pièce de la scène, ou `null` — D-333.
 *
 * ⚠️ Une COPIE de répétition n'a pas de lien propre (`linkId: null`) : elle se règle par
 * le lien de sa SOURCE (`sourceLinkId`), dont elle partage les réponses (D-332, v1).
 * Sans cette lecture, aucune copie ne serait sélectionnable, et rien ne le dirait.
 *
 * ⚠️ **La source est `sourceKey`, publiée par le moteur (D-375)** — et non `occurrence.of`,
 * qui ne fait qu'UN pas : la copie d'une copie (le quatrième bras du JeNo, deux miroirs
 * enchaînés) a pour `of` une autre copie, que les placements ne connaissent pas. Elle
 * n'était donc pas sélectionnable. `occurrence.of` ne reste lu que pour une projection
 * d'avant D-375.
 *
 * @param {object} model  le modèle de la page (`toViewModel`)
 * @param {Array} pieces  la projection du moteur (`projectAssemblyPieces`)
 * @param {string} nodeId l'identité de la pose
 */
export function placementOf(model, pieces, nodeId) {
    const placements = (model && model.placements) || {};
    const piece = (pieces || []).find((p) => p.key === nodeId);
    if (!piece) return null;
    // ⚠️ **PAR L'IDENTITÉ DE NŒUD, jamais recomposée depuis le lien.** Les placements sont
    // rangés sous l'`id` du nœud de la définition ; depuis D-349 un nœud IMBRIQUÉ porte le
    // chemin de sa pose (`c10/c11`), et `c${linkId}` ne le nomme plus. La clé de la pièce
    // EST cet id ; une copie de répétition renvoie à celui de sa source (`occurrence.of`).
    return placements[piece.key] || placements[piece.sourceKey]
        || placements[piece.occurrence?.of] || null;
}

/**
 * La FAMILLE d'une pose : toutes les poses du même placement — l'original, ses copies de
 * répétition et de miroir, et les copies de ses copies (D-375).
 *
 * Arbitrage de Gerry (2026-09-29) : *« la sélection d'une occurrence sélectionne les autres
 * ainsi que l'original »*. Elles partagent leurs réponses (D-332, D-175 fermé) : allumer
 * la seule pose touchée laisserait croire qu'une couleur choisie ne vaut que pour elle.
 *
 * ⓘ Deux LIENS vers la même pièce ne sont pas une famille : chacun a ses réponses.
 *
 * @param {Array} pieces   la projection du moteur (`projectAssemblyPieces`)
 * @param {string} nodeId  la pose touchée
 * @returns {Array<string>} les clés de la famille, la pose touchée EN TÊTE
 */
export function familyOf(pieces, nodeId) {
    if (!nodeId) return [];
    const touched = (pieces || []).find((p) => p.key === nodeId);
    const source = touched?.sourceKey;
    if (!source) return [nodeId];
    const others = (pieces || [])
        .filter((p) => p.sourceKey === source && p.key !== nodeId)
        .map((p) => p.key);
    return [nodeId, ...others];
}

/** Les poses SÉLECTIONNABLES — celles qui ont un placement réglable (arbitrage Gerry). */
export function selectableNodeIds(model, pieces) {
    return new Set((pieces || []).filter((p) => placementOf(model, pieces, p.key)).map((p) => p.key));
}

/**
 * Ce qu'il faut envoyer pour répondre à une question d'un PLACEMENT — mêmes refus que
 * `answerFor`, et le lien en plus (D-332).
 */
export function answerForPlacement(model, placement, questionId, valueId) {
    if (!model || model.error || model.closed || !placement) return null;
    const question = (placement.questions || []).find((q) => q.id === questionId);
    const value = question?.values.find((v) => v.id === valueId);
    if (!value || !value.available) return null;
    if (value.chosen && !question.multi) return null;
    return { attribute_id: questionId, value_id: valueId, link_id: placement.linkId };
}

/** Ce que la page montre pour une valeur — et pourquoi elle est éteinte, s'il y a lieu. */
function toValue(raw) {
    return {
        id: raw.id,
        name: raw.name,
        // La forme RANGÉE — le nombre nu d'une question numérique (D-160). C'est elle
        // qu'un champ de saisie affiche ; le libellé, lui, porte l'unité.
        raw: raw.raw ?? null,
        // La pastille et la vignette, telles que le serveur les range. `null` veut
        // dire « il n'y en a pas » — jamais « on ne sait pas ».
        color: raw.color || null,
        image: raw.image || null,
        available: raw.available !== false,
        chosen: !!raw.chosen,
        // ⚠️ Une valeur indisponible reste AFFICHÉE et CLIQUABLE : c'est D-178 — un appui
        // doit pouvoir en donner la raison. `disabled` interdirait l'appui, donc la
        // raison. Ce qui se refuse est la SÉLECTION, pas l'interaction.
        muted: raw.available === false,
        // ⓘ Les catégories de la réponse, par clé (D-382) — les pastilles du panneau.
        // ⚠️ Recopiées ICI, faute de quoi elles s'arrêteraient à cette fonction ([[L-212]]).
        categoryKeys: Array.isArray(raw.categoryKeys) ? raw.categoryKeys : [],
    };
}

/**
 * La réponse du serveur, mise en forme pour l'écran.
 *
 * @param {object} payload ce que rend `/configurator/state`
 * @param {object} [previous] le modèle précédent — pour garder ce qui n'a pas changé
 */
export function toViewModel(payload, previous = null) {
    if (!payload || payload.error) {
        return {
            error: payload?.error || "unknown_session",
            // ⚠️ Le message est ICI, pas au serveur : celui-ci répond par un CODE, et
            // trois refus y portent le même (jeton absent, inconnu, périmé) pour ne pas
            // dire à qui tâtonne quels jetons ont existé (D-190).
            message: _t("This configuration link is not valid any more."),
            questions: [],
        };
    }
    // ⚠️ `previous &&` EN TÊTE, et ce n'est pas une précaution de style : sans
    // modèle précédent, `previous?.definition` vaut `undefined` — et si la charge
    // n'a pas de clé `definition`, `sameDefinition(undefined, undefined)` rend
    // VRAI, donc on lisait `previous.definition` sur `null`. En production la clé
    // est toujours là, ce qui rendait le défaut invisible ; un appel sans elle le
    // fait tomber (trouvé par les tests, 2026-09-06).
    const definition = previous && sameDefinition(previous.definition, payload.definition)
        ? previous.definition
        : payload.definition || null;
    return {
        error: null,
        productName: payload.productName || "",
        price: payload.price || 0,
        // ⓘ D-368 — le TOTAL affiché (le produit plus ses lignes à part), et ces lignes,
        // qui partent au devis ou au panier rattachées à celle du produit.
        total: payload.total ?? payload.price ?? 0,
        separateLines: payload.separateLines || [],
        noVariantPtavIds: payload.noVariantPtavIds || [],
        closed: payload.state && payload.state !== "draft",
        questions: (payload.attributes || []).map(toQuestion),
        // ⓘ D-385 — les ÉTAPES visibles, dans l'ordre ; vide sans étape déclarée.
        steps: (payload.steps || []).map(toStep),
        // ⚠️ **LES PLACEMENTS RÉGLABLES** (D-332, D-333) : les pièces posées dont des
        // questions restent à répondre — et elles seules. C'est la vérité UNIQUE de
        // « sélectionnable » sur cette page ; leurs questions ont la forme de celles de
        // la racine, et se rendent avec le même gabarit.
        placements: toPlacements(payload.placements),
        definition,
        scope: payload.scope || {},
        // ⓘ Toujours un objet : « personne ne conduit » se lit `{holder: null}`,
        // jamais par une absence — sans quoi un état ancien et un état libre
        // seraient indistinguables.
        hand: payload.hand || { holder: null, label: null },
        // L'attente a un visage (2026-09-06) : la photo du produit tient la place
        // de la 3D, et la VUE d'où elle a été prise sert à s'y poser exactement.
        image: payload.image || null,
        camera: payload.camera || null,
        // Les MATIÈRES de la scène, composées par le serveur : la page n'a le droit
        // de lire aucun des modèles qui les portent.
        // ⚠️ Les ZONES et l'AMBIANCE gardent aussi leur référence quand rien n'a changé :
        // le viewer les compare par identité, et les zones seules reconstruisent la scène.
        // L'écho du bus — la même réponse, reçue une seconde fois — refaisait tout
        // ([[L-449]]).
        zones: keepIfSame(previous?.zones, payload.zones || null),
        productId: payload.productId || null,
        // ⓘ **LA SORTIE de la page atteinte par un lien** — la fiche du produit. Elle vient
        // du serveur parce que la route de la page ne résout pas le jeton (D-190), et elle
        // vaut `null` sur une base sans site : la croix ne se dessine alors pas, plutôt que
        // de mener nulle part.
        productUrl: payload.productUrl || null,
        // ⚠️ **LA CUISSON ET L'AMBIANCE TRAVERSENT — et elles ne le faisaient PAS.** Le
        // serveur les émettait (`web_state`), la page les lisait (`model.baked`,
        // `model.ambience`), et cette fonction — une LISTE BLANCHE — les laissait tomber
        // ([[L-212]] : une transformation qui recopie champ par champ perd tout ce qu'on
        // ajoute en amont). Le chemin des GLB cuits n'avait donc JAMAIS tourné sur la page
        // publique, et l'ambiance du produit n'atteignait pas le viewer — sans une erreur,
        // et sous des gardes vertes qui lisaient le TEXTE de la page, jamais la donnée.
        // Relevé le 2026-09-22 sur le JeNo : `baked: null`, `ambience: non`.
        baked: payload.baked || null,
        // ⚠️ Même maillon, même piège : un champ servi que cette recopie oublie n'atteint
        // jamais la page ([[L-357]]). Les fichiers importés, et leur URL à jeton.
        imported: payload.imported || null,
        ambience: keepIfSame(previous?.ambience, payload.ambience || null),
    };
}

/**
 * Les deux définitions décrivent-elles la même RECETTE ?
 *
 * ⓘ Comparaison par sérialisation : la définition est un arbre de données pures, sans
 * cycle (c'est la garantie de `to_definition`), et elle se compte en dizaines de nœuds. Une
 * comparaison structurelle écrite à la main coûterait plus cher à maintenir qu'à exécuter.
 */
function keepIfSame(previous, next) {
    return previous && sameDefinition(previous, next) ? previous : next;
}

export function sameDefinition(a, b) {
    if (a === b) return true;
    if (!a || !b) return false;
    return JSON.stringify(a) === JSON.stringify(b);
}

/**
 * Ce qu'il faut envoyer quand on clique une valeur — ou `null` si rien ne doit partir.
 *
 * ⚠️ **Trois clics ne valent rien**, et chacun pour sa raison : sur une valeur déjà
 * choisie (le serveur écrirait la même chose et la page clignoterait), sur une valeur
 * indisponible (elle n'est pas un choix, c'est une explication à donner), et sur une
 * configuration close (elle a donné sa variante — D-190).
 */
export function answerFor(model, questionId, valueId) {
    if (!model || model.error || model.closed) return null;
    const question = (model.questions || []).find((q) => q.id === questionId);
    const value = question?.values.find((v) => v.id === valueId);
    if (!value || !value.available) return null;
    // ⚠️ **RE-CLIQUER UNE RÉPONSE DÉJÀ RETENUE NE VAUT RIEN — SAUF SI ELLE EST
    // MULTIPLE.** Sur une question à réponse unique, le serveur réécrirait la
    // même chose et la page clignoterait ; sur une question à cases, c'est le
    // geste qui DÉCOCHE, et le refuser rendrait un choix irréversible.
    if (value.chosen && !question.multi) return null;
    return { attribute_id: questionId, value_id: valueId };
}

/**
 * Qui conduit, vu de CETTE page — D-255.
 *
 * @param {object} model le modèle courant
 * @param {string} me    l'identifiant de cette page (un par onglet)
 * @returns {{free: boolean, mine: boolean, label: ?string}}
 */
export function handState(model, me) {
    const hand = (model && model.hand) || {};
    if (!hand.holder) return { free: true, mine: false, label: null };
    return { free: false, mine: hand.holder === me, label: hand.label || null };
}

/**
 * Ce qu'on dit à qui ne conduit pas — ou `null` s'il conduit.
 *
 * ⚠️ Le message NOMME celui qui tient la main. « Modification impossible » est
 * la seule réponse dont on ne peut rien faire : on ne sait ni pourquoi, ni
 * jusqu'à quand, ni qui aller voir.
 */
export function handMessage(hand) {
    if (!hand || hand.free || hand.mine) return null;
    return hand.label
        ? _t("%s is configuring. Take over to make a change.", hand.label)
        : _t("Someone else is configuring. Take over to make a change.");
}

/**
 * Ce que la page DIT quand la confirmation est refusée — ou `null` si elle a réussi.
 *
 * ⚠️ Un refus de confirmation n'est PAS une réponse d'état : le passer à `toViewModel`
 * effacerait la configuration à l'écran pour afficher « ce lien n'est plus valable »,
 * alors que la page est parfaitement vivante et qu'il manque juste une réponse.
 */
export function confirmError(payload) {
    if (!payload || !payload.error) return null;
    if (payload.error === "incomplete") {
        const missing = (payload.missing || []).join(", ");
        // ⓘ On NOMME ce qui manque : « configuration incomplète » n'aide personne
        // sur un produit qui pose quinze questions.
        return missing
            ? _t("Please answer first: %s", missing)
            : _t("Some required answers are missing.");
    }
    if (payload.error === "session_closed") {
        return _t("This configuration is already confirmed.");
    }
    if (payload.error === "not_holding") {
        // ⓘ Le serveur rend l'état de la main AVEC son refus : la page peut donc
        // nommer celui qui conduit sans redemander l'état complet.
        return handMessage({ free: false, mine: false, label: payload.hand?.label });
    }
    return _t("This configuration link is not valid any more.");
}

/**
 * Ce que la page DIT quand une SAISIE est refusée — ou `null` si elle a été retenue.
 *
 * ⚠️ Comme pour la confirmation, un refus n'est PAS un état : le passer à `toViewModel`
 * effacerait la page pour « ce lien n'est plus valable », alors qu'il suffit de corriger
 * un nombre. Le message d'une saisie invalide vient du SERVEUR, déjà traduit : c'est lui
 * qui connaît la borne, le pas, la condition qui l'impose et la valeur la plus proche.
 */
export function customError(payload) {
    if (!payload || !payload.error) return null;
    if (payload.error === "invalid_custom") {
        return payload.message || _t("This answer is not accepted.");
    }
    if (payload.error === "custom_not_allowed") {
        return _t("This question does not accept a typed answer.");
    }
    return confirmError(payload);
}

/**
 * La raison pour laquelle une valeur est éteinte — D-178, *« un appui donne la raison »*.
 *
 * ⓘ Ce que la page peut dire aujourd'hui est court, et c'est assumé : le serveur rend
 * `available`, pas le POURQUOI. Nommer les conditions qui ferment une valeur demande le
 * pont du lot 4 (D-170), et cette fonction est l'endroit qui l'attend.
 */
export function reasonFor(value) {
    if (!value || value.available) return null;
    return _t("Not available with your current choices.");
}

/**
 * Le lecteur des pièces CUITES — un fichier se lit et se décode UNE fois pour la vie de la
 * page ([[L-449]]).
 *
 * ⚠️ **La page relisait tout, à chaque reconstruction.** « Tête bombée de vis.glb » sert
 * quinze poses du JeNo : il était téléchargé et décodé quinze fois à CHAQUE permutation
 * (1,7 à 4,9 s par clic, mesuré le 2026-09-29), pour un fichier qui n'avait pas changé.
 * L'éditeur tient ce cache depuis sa cuisson (`_readBakedFile`) ; la page ne l'avait pas.
 *
 * ⓘ **La clé est l'URL servie ET la table des faces.** L'URL porte le jeton de la pièce
 * jointe, qui ne change pas ; une nouvelle cuisson est une nouvelle pièce jointe, donc une
 * nouvelle clé. Les poses d'un même fichier partagent ses volumes, comme dans l'éditeur :
 * le moteur les pose par leur `worldTransform`, il ne les modifie pas.
 *
 * ⓘ **La PROMESSE est gardée, pas le résultat** : quinze poses demandées dans le même tour
 * n'ouvrent qu'un téléchargement. Un échec n'est pas mémorisé, il se retente au tour suivant
 * ([[L-323]]).
 *
 * @param {(url: string, faces: object) => Promise<Array>} readFile  lit et décode un fichier,
 *        rend ses volumes (`bakedSolidsFromScene`)
 * @param {{onError?: (nodeId: string, error: Error) => void}} [options]
 * @returns {{read: (baked: object) => Promise<Map>, size: number}} `read` rend la forme que le
 *          moteur attend, `Map(nodeId → {solids})`
 */
export function createBakedReader(readFile, { onError = () => {} } = {}) {
    const files = new Map();
    const fileOf = (url, faces) => {
        const key = `${url}\n${JSON.stringify(faces)}`;
        let pending = files.get(key);
        if (!pending) {
            pending = Promise.resolve().then(() => readFile(url, faces));
            files.set(key, pending);
            pending.catch(() => {
                if (files.get(key) === pending) files.delete(key);
            });
        }
        return pending;
    };
    return {
        async read(baked) {
            const loaded = new Map();
            await Promise.all(Object.entries(baked || {}).map(async ([nodeId, entry]) => {
                // ⚠️ L'URL SERVIE porte le jeton d'accès : sans lui, un visiteur anonyme
                // reçoit un 404 et la pièce manque. Le repli sur l'identifiant nu ne vaut
                // que pour un serveur plus ancien.
                const url = entry?.url || `/web/content/${entry?.attachmentId}`;
                try {
                    const solids = await fileOf(url, entry?.faces || {});
                    if (solids?.length) loaded.set(nodeId, { solids });
                } catch (error) {
                    onError(nodeId, error);
                }
            }));
            return loaded;
        },
        get size() {
            return files.size;
        },
    };
}
