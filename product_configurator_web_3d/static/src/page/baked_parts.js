/** @odoo-module */
/**
 * baked_parts.js — SERVIR une piece deja cuite au lieu de la reconstruire.
 *
 * ─ Pourquoi ce module existe ─────────────────────────────────────────────────
 *
 * Mesure du projet GLB (D-232, JeNo 5") : le goulot est la CONSTRUCTION MOTEUR —
 * 1 177 ms, 76 % du temps. D-235 a ferme la question du poids : avec Draco et la cuisson
 * geometrique, 385 Kio sur le fil et un seuil de 2,7 Mbit/s, pour 62 ms de decodage. La
 * piece qui ne depend d'aucune reponse n'a donc aucune raison d'etre rebatie a chaque
 * ouverture de page.
 *
 * ─ ⚠️ LE POINT D'INSERTION, et pourquoi c'est celui-la ───────────────────────
 *
 * `build()` recoit le constructeur de piece en CALLBACK. Il suffit donc de l'envelopper :
 * un noeud deja cuit rend sa piece toute faite, les autres passent a `buildPart`. Rien
 * d'autre ne bouge — ni l'arbre, ni les poses, ni la projection.
 *
 * ⚠️ **Mais `build()` est SYNCHRONE**, et charger un fichier ne l'est pas. Les GLB sont
 * donc charges AVANT, et le constructeur ne fait que consulter une table deja remplie.
 * C'est exactement ce que l'editeur fait de ses geometries importees, et pour la meme
 * raison.
 *
 * ─ ⓵ REPOSER LES MATIERES : la table des faces revient sur la geometrie ─────
 *
 * Le viewer peint en lisant `geometry.userData.faces` et en en derivant des PLAGES DE
 * TRIANGLES. Il suffit donc de reposer cette table sur la geometrie chargee pour que la
 * peinture par zones fonctionne exactement comme dans l'editeur — sans une ligne de code de
 * peinture ici.
 *
 * ⚠️ **Deux conditions, et les deux sont tenues a la cuisson.** L'export ecrit UNE SEULE
 * PRIMITIVE par maille (materiau unique force), donc l'index n'est pas redecoupe et les
 * plages restent valides. Et la table est rangee PAR SOLIDE, si bien qu'on la retrouve par
 * le nom de la maille — `<pieceKey>#<nodeId>` — sans rien deviner. A plat, il aurait fallu
 * inferer par le prefixe d'identifiant, ce qui echoue en silence sur un solide ne d'un
 * booleen, lequel agrege les faces de PLUSIEURS fonctions.
 */

/**
 * Les mailles d'une scene chargee, a plat.
 *
 * ⓘ Le critere est `isMesh` et rien d'autre : le fichier ne contient que ce que l'export y
 * a mis, et l'export ne prend que les solides visibles.
 */
export function meshesOf(scene) {
    const out = [];
    const visit = (object) => {
        if (!object) return;
        if (object.isMesh && object.geometry) out.push(object);
        for (const child of object.children || []) visit(child);
    };
    visit(scene);
    return out;
}

/**
 * Les SOLIDES d'une piece cuite — la moitie qui decide, sans THREE.
 *
 * ⚠️ **`nodeId` est celui de la PIECE, jamais le nom de la maille dans le fichier.** Le
 * viewer indexe les solides par noeud et les cherche par celui de la piece qu'il monte : y
 * mettre le nom du fichier les rendrait introuvables, et la piece s'afficherait vide sans
 * la moindre erreur. C'est la lecon que le chemin des imports porte deja.
 *
 * @param {object} scene       la scene glTF chargee
 * @param {object} spec
 * @param {string} spec.nodeId identite du noeud dans l'arbre construit
 * @param {Array} [spec.faces] la table des faces, telle que le moteur l'avait publiee
 * @returns {Array<object>} un descripteur de solide par maille
 */
export function facesOfMesh(mesh, faces) {
    const name = mesh?.name || "";
    const cut = name.indexOf("#");
    const key = cut >= 0 ? name.slice(cut + 1) : name;
    return (faces && faces[key]) || [];
}

export function bakedSolids(scene, { nodeId, faces = {} } = {}) {
    return meshesOf(scene).map((mesh) => ({
        fnId: null,
        nodeId,
        // ⓘ Le nom du fichier est conserve pour le RELEVE, jamais pour l'identite :
        // `pieceKey#nodeId`, ecrit par l'export, dit d'ou vient cette maille.
        bakedName: mesh.name || null,
        geometry: mesh.geometry,
        importedMaterial: mesh.material || null,
        // ⚠️ **ET ELLE REVIENT SUR LA GEOMETRIE**, pas seulement sur le descripteur : c'est
        // `geometry.userData.faces` que le viewer lit pour peindre. La poser ailleurs
        // laisserait la piece grise, sans la moindre erreur.
        faces: applyFacesTo(mesh, faces),
        op: "bakedGlb",
        resolved: {},
        sketchName: null,
        scale: [1, 1, 1],
        extrusionAxis: null,
        extrusionLength: 0,
        booleanMode: "none",
        imported: true,
        // ⚠️ Le drapeau qui compte : le viewer ne PEUT pas reproduire cette forme par son
        // cache `(dessin, op, params)` — elle ne vient d'aucun dessin. Sans lui il
        // rebatirait une piece vide, et le fichier resterait invisible.
        engineOwned: true,
    }));
}

/** Repose la table des faces sur la GEOMETRIE, et la rend. */
function applyFacesTo(mesh, faces) {
    const own = facesOfMesh(mesh, faces);
    if (own.length) {
        mesh.geometry.userData = mesh.geometry.userData || {};
        mesh.geometry.userData.faces = own;
    }
    return own;
}

/**
 * La PIECE d'un noeud deja cuit — la forme que `build()` attend d'un constructeur.
 *
 * ⓘ THREE est injecte : ce module ne l'importe pas, comme tout ce qui est eprouvable hors
 * navigateur dans ce depot.
 *
 * @returns {?object} `null` quand rien n'est cuit pour ce noeud — l'appelant enchaine alors
 *          sur `buildPart`, et c'est ce qui rend la substitution sans risque.
 */
export function bakedPart(THREE, node, worldTransform, loaded) {
    const entry = loaded?.get?.(node?.id);
    if (!entry?.scene) return null;
    const localToWorld = worldTransform ? worldTransform.clone() : new THREE.Matrix4();
    const solids = bakedSolids(entry.scene, { nodeId: node.id, faces: entry.faces });
    if (!solids.length) return null;
    const box = new THREE.Box3();
    for (const solid of solids) {
        if (!solid.geometry.boundingBox) solid.geometry.computeBoundingBox();
        box.union(solid.geometry.boundingBox.clone().applyMatrix4(localToWorld));
        solid.localToWorld = localToWorld;
    }
    return {
        worldTransform: worldTransform || null,
        sketches: [], tools: [], errors: [],
        solids,
        faces: Object.values(entry.faces || {}).flat(),
        bboxWorld: { min: box.min.toArray(), max: box.max.toArray() },
    };
}
