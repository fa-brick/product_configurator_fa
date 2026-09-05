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

/** Ce que la page montre pour une valeur — et pourquoi elle est éteinte, s'il y a lieu. */
function toValue(raw) {
    return {
        id: raw.id,
        name: raw.name,
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
    const definition = sameDefinition(previous?.definition, payload.definition)
        ? previous.definition
        : payload.definition || null;
    return {
        error: null,
        productName: payload.productName || "",
        price: payload.price || 0,
        closed: payload.state && payload.state !== "draft",
        questions: (payload.attributes || []).map((line) => ({
            id: line.id,
            name: line.name,
            required: !!line.required,
            multi: !!line.multi,
            values: (line.values || []).map(toValue),
        })),
        definition,
        scope: payload.scope || {},
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
    if (!value || !value.available || value.chosen) return null;
    return { attribute_id: questionId, value_id: valueId };
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
