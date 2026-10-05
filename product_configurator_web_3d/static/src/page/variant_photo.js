/** @odoo-module */
/**
 * LA PHOTO D'UNE VARIANTE NÉE D'UNE CONFIGURATION — D-399, lot 5 (voie A).
 *
 * Gerry, 2026-10-05 : *« A pour l'ajout au panier puis B quand c'est possible »*, *« pour tout
 * devis / commande dont le variant n'est pas créé »*. Quand la confirmation CRÉE la variante,
 * le serveur joint à son état la prise de vue à rejouer (`state.photo` : la vue de l'appareil
 * photo, le décor, les surfaces d'ombre, le cadre commun des variantes). La page la rejoue
 * avec SON viewer, hors de l'orbite où le client l'a laissé, et envoie l'image.
 *
 * ⚠️ **Une image perdue n'empêche jamais un achat.** Tout tient dans un budget (4 s) ; au-delà,
 * on part au panier sans elle — l'éditeur la fera (voie B), le compteur et l'activité le
 * rappelleront.
 *
 * ⓘ Un fichier à lui (règle de Gerry : code neuf, fichier neuf) ; la page n'y délègue que
 * par une ligne dans `onConfirm`, et le retour du viewer.
 */

export const PHOTO_BUDGET_MS = 4000;

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const nextFrame = () => new Promise((resolve) => {
    const raf = globalThis.requestAnimationFrame;
    if (raf) raf(() => resolve()); else setTimeout(resolve, 16);
});

/** La promesse, ou `null` si elle n'a pas abouti avant `ms`. */
export function withTimeout(promise, ms) {
    return Promise.race([promise, delay(Math.max(ms, 0)).then(() => null)]);
}

/** UNE photo par le chemin ordinaire du viewer (`thumbnailRequest`). */
export function capturePhoto(page, photo) {
    return new Promise((resolve) => {
        page._photoResolve = resolve;
        page.state.photoRequest = {
            ...photo,
            serial: (page.state.photoRequest?.serial ?? 0) + 1,
        };
    });
}

/** Le retour du viewer — branché sur `onThumbnailCaptured` de la page. */
export function photoCaptured(page, b64) {
    const resolve = page._photoResolve;
    page._photoResolve = null;
    page.state.photoRequest = null;
    resolve?.(b64 || null);
}

/**
 * Photographier la variante confirmée et l'envoyer — dans le budget, ou pas du tout.
 *
 * @returns {Promise<boolean>} vrai si l'image a été enregistrée
 */
export async function sendVariantPhoto(page, photo, productId, { budget = PHOTO_BUDGET_MS } = {}) {
    if (!photo || !productId) return false;
    const deadline = Date.now() + budget;
    try {
        // ⓘ Une pièce ISOLÉE par un double clic ne montrerait qu'elle : on rend la scène
        // entière avant la photo.
        if (page.state.selection?.isolated) page._select?.(null, false);
        let b64 = null;
        while (!b64 && Date.now() < deadline) {
            await nextFrame();
            await nextFrame();
            // Le viewer rend `null` tant que l'environnement ou des textures manquent
            // ([[L-448]]) : on redemande, dans le budget.
            b64 = await withTimeout(capturePhoto(page, photo), deadline - Date.now());
            if (!b64) await delay(200);
        }
        if (!b64) return false;
        const answer = await withTimeout(
            page._call("/configurator/variant_image", { product_id: productId, image: b64 }),
            Math.max(deadline - Date.now(), 1500));
        return !!answer?.ok;
    } catch (error) {
        console.warn("[configurateur] image de variante non envoyée :", error);
        return false;
    } finally {
        page._photoResolve = null;
        page.state.photoRequest = null;
    }
}
