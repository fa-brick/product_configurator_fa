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
        values: (line.values || []).map(toValue),
    };
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
    return placements[piece.key] || placements[piece.occurrence?.of] || null;
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
        closed: payload.state && payload.state !== "draft",
        questions: (payload.attributes || []).map(toQuestion),
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
        zones: payload.zones || null,
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
        ambience: payload.ambience || null,
    };
}

/**
 * Les deux définitions décrivent-elles la même RECETTE ?
 *
 * ⓘ Comparaison par sérialisation : la définition est un arbre de données pures, sans
 * cycle (c'est la garantie de `to_definition`), et elle se compte en dizaines de nœuds. Une
 * comparaison structurelle écrite à la main coûterait plus cher à maintenir qu'à exécuter.
 */
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
