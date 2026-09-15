/** @odoo-module */
/**
 * viewer_props.test.js — Ce que la page DOIT donner au viewer.
 *
 * ⚠️ **Une prop absente ne lève pas.** Le viewer se rabat sur ce qu'il sait faire
 * seul — refaire une extrusion depuis son dessin — et rend une pièce PLAUSIBLE et
 * fausse : sans ses trous, sans ses chanfreins, sans ses matières. Relevé de Gerry
 * le 2026-09-07, sur la plaque du JeNo ; aucun test ne pouvait le voir, et la
 * console restait muette ([[L-188]]).
 *
 * ⓘ On éprouve donc le GABARIT : ces quatre props sont le contrat entre la page et
 * le viewer, et leur oubli est silencieux par construction.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const TEMPLATE = readFileSync(
    join(__dirname, "..", "src", "page", "configurator_page.xml"), "utf8");

/** Le bloc de la balise `<PartViewer3D …>`, attributs compris. */
function viewerTag() {
    const start = TEMPLATE.indexOf("<PartViewer3D");
    expect(start).toBeGreaterThan(-1);
    return TEMPLATE.slice(start, TEMPLATE.indexOf("/>", start));
}

/**
 * ⚠️ **La CAMÉRA se demande avant le premier rendu.** Posée après la construction,
 * elle arrivait 2,5 s trop tard : le viewer avait déjà cadré la scène tout seul, et
 * l'on voyait la pièce à deux endroits (sonde du 2026-09-07 — cadrage automatique à
 * 2 405 ms, vue par défaut à 4 899 ms ; après correction : 2 437 et 2 440 ms).
 *
 * ⓘ On éprouve le CHEMIN, pas le chronomètre : la demande doit partir de
 * `onWillStart`, là où l'état arrive, et non du seul `_applyModel` — le premier
 * chargement ne passe pas par lui, et c'est justement celui qui compte.
 */
describe("la vue par défaut de la page", () => {
    const SOURCE = readFileSync(
        join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");

    /** Le corps d'une méthode ou d'un bloc, depuis son entête. */
    function bodyAfter(marker) {
        const start = SOURCE.indexOf(marker);
        expect(start).toBeGreaterThan(-1);
        return SOURCE.slice(start, start + 1400);
    }

    test("elle est demandée dès l'arrivée de l'état, dans `onWillStart`", () => {
        expect(bodyAfter("onWillStart(async () => {")).toContain("_settleCamera()");
    });

    test("elle est demandée aussi quand l'état est REMPLACÉ", () => {
        expect(bodyAfter("async _applyModel(payload)")).toContain("_settleCamera()");
    });

    test("elle ne se demande QU'UNE FOIS — sinon un clic ramènerait la caméra", () => {
        expect(bodyAfter("_settleCamera() {")).toContain("_cameraSettled");
    });

    test("la photo s'efface quand la SCÈNE est là, pas quand la caméra se pose", () => {
        // Les deux étaient liés : lever `ready` dans `_settleCamera` faisait dépendre
        // l'attente d'une pose, et la pose d'une construction.
        expect(bodyAfter("_settleCamera() {")).not.toContain("state.ready = true");
    });
});

describe("la page publique et son viewer", () => {
    const tag = viewerTag();

    test("elle passe les POSES calculées par le moteur", () => {
        expect(tag).toContain("getResolvedWorldByNodeId");
    });

    test("elle passe les VOLUMES du moteur — percés, chanfreinés", () => {
        // Sans eux : plus de perçage, plus de chanfrein, et rien ne le dit.
        expect(tag).toContain("getResolvedSolidsByNodeId");
    });

    test("elle passe l'identité de la PIÈCE racine — sinon aucune matière", () => {
        // Les zones sont rangées par pièce (D-166) : sans cet identifiant, elles
        // ne trouvent personne et la racine reste grise.
        expect(tag).toContain("rootPieceId");
    });

    test("elle passe le NŒUD racine — par lui, son volume construit", () => {
        expect(tag).toContain("rootNodeId");
    });

    test("elle NE DESSINE PAS les traits d'esquisse", () => {
        // Le dessin sert à éditer. Sur un écran où l'on ne peut rien modifier, ses
        // traits font passer une gravure pour un contour posé sur la pièce.
        expect(tag).toContain('showSketchLines="false"');
    });

    test("elle passe les zones de matière", () => {
        expect(tag).toContain("zonesByPiece");
    });

    test("⚠️ et PLUS `zoneMaterialsByNode` — la prop a été retirée, pas oubliée", () => {
        // Elle alimentait les EXCEPTIONS de matière par placement, parties avec les canaux
        // de réponses le 2026-09-08 (D-268, commit 5fd3b4d) : sans canal, il n'y a plus
        // rien à apparier. Le viewer ne la déclare plus non plus.
        //
        // ⚠️ **Ce test l'a réclamée pendant SEPT JOURS**, rouge et muet — le commit qui
        // retirait la prop n'a pas touché à son test, et la suite Jest de ce dépôt n'est
        // pas dans le réflexe. C'est la seconde fois en une semaine dans ce projet, après
        // deux tests de caméra restés rouges quatre jours pour la même raison.
        //
        // ⓘ Il reste ici en NÉGATIF plutôt que d'être effacé : si la prop revient un jour,
        // c'est une décision, et elle doit se voir.
        expect(tag).not.toContain("zoneMaterialsByNode");
    });
});


describe("la carte d'une réponse, quand elle n'a pas de vignette", () => {
    const TEMPLATE_PAGE = readFileSync(
        join(__dirname, "..", "src", "page", "configurator_page.xml"), "utf8");

    test("le CADRE ne se dessine que s'il y a une image", () => {
        // ⚠️ Un cadre vide se lit comme un chargement en panne. Une valeur qui ne
        // désigne rien n'a pas d'image : la carte se réduit à son libellé
        // (relevé de Gerry, 2026-09-07).
        expect(TEMPLATE_PAGE).toContain('<span t-if="value.image" class="o_cfg3d_card_shot">');
    });

    test("le libellé, lui, reste toujours là", () => {
        expect(TEMPLATE_PAGE).toContain('class="o_cfg3d_card_label"');
    });
});

describe("le dialogue n'ajoute pas sa marge autour de la scène", () => {
    const SCSS_ACTION = readFileSync(
        join(__dirname, "..", "src", "page", "configurator_action.scss"), "utf8");

    test("le corps du dialogue perd le `padding` d'Odoo", () => {
        expect(SCSS_ACTION.replace(/\s+/g, " ")).toContain("o_cfg3d_action) { padding: 0;");
    });
});
