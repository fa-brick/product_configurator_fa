/** @odoo-module */
/**
 * website_preview_exit.js — Le configurateur ne s'ouvre jamais dans l'aperçu du site (D-540).
 *
 * ⚠️ Dans le cadre de `website.website_preview`, le clavier du téléphone ne réduit pas la partie visible de la page :
 *   le calage au-dessus du clavier ne joue pas, et le pavé numérique se referme seul ([[L-637]]).
 * ⓘ Seul un cadre de la MÊME origine a un `frameElement` : un site tiers qui intègrerait la page n'est pas visé.
 * Source : https://developer.mozilla.org/en-US/docs/Web/API/Window/frameElement
 */

/** La page est-elle chargée dans un cadre du back-office (aperçu ou édition du site) ? */
export function inOdooFrame(win = globalThis.window) {
    return !!win?.frameElement;
}

/**
 * Recharger la page dans la fenêtre entière, à la même adresse.
 * ⚠️ `replace` : un retour arrière qui ramènerait la page dans le cadre la ferait ressortir aussitôt.
 */
export function leaveOdooFrame(win = globalThis.window) {
    if (!inOdooFrame(win)) return false;
    win.top.location.replace(win.location.href);
    return true;
}

// ⓘ Seulement sur la page du configurateur : le bundle du site charge ce fichier sur toutes les pages.
function onPageReady() {
    if (document.body?.classList.contains("o_cfg3d_body")) leaveOdooFrame();
}

if (globalThis.document) {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", onPageReady);
    } else {
        onPageReady();
    }
}
