/** @odoo-module */
/**
 * scene_rebuild.test.js — Ce qu'une PERMUTATION a le droit de reconstruire.
 *
 * ⚠️ **Une graine absente ne lève pas, ne se voit pas, et ne se mesure qu'au
 * chronomètre.** `build()` reparti sans rien refait l'arbre ENTIER — booléens compris —
 * pour une seule pose neuve. Mesuré le 2026-09-22 sur le JeNo, au travers du serveur
 * d'essai : **2 742 ms sans graine, 1 616 ms avec**, les douze autres pièces annoncées
 * « semée » à 0 ms. L'écran, lui, est identique dans les deux cas : rien ne dit qu'on paie.
 *
 * ⓘ On éprouve la SOURCE, comme `viewer_props.test.js` — l'éditeur n'est pas dans ce
 * dépôt (son moteur y est un bouchon), et ce qui doit tenir est le contrat de l'appel.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const SOURCE = readFileSync(
    join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");

/** Le corps de `_buildScene`, depuis son entête jusqu'au `catch`. */
function buildScene() {
    const start = SOURCE.indexOf("async _buildScene(");
    expect(start).toBeGreaterThan(-1);
    const end = SOURCE.indexOf("} catch (e) {", start);
    expect(end).toBeGreaterThan(start);
    return SOURCE.slice(start, end);
}

describe("la reconstruction de la scène après un clic", () => {
    test("elle SÈME la passe précédente — sans quoi tout l'arbre se refait", () => {
        expect(buildScene()).toContain("sharedSeed: this._sharedParts");
    });

    test("elle RETIENT ce que la passe a servi, sinon la graine suivante est vide", () => {
        const corps = buildScene();
        expect(corps).toContain("sharedOut");
        expect(corps).toContain("this._sharedParts = sharedOut");
    });

    test("la carte de sortie est NEUVE : ce qui n'a pas servi ne repasse pas", () => {
        expect(buildScene()).toContain("const sharedOut = new Map();");
    });

    /**
     * ⚠️ Sans ce drapeau, une pose servie par son GLB à la passe d'avant serait rendue
     * telle quelle à une passe qui n'a plus son fichier : la signature ne porte que la
     * recette, et la recette ne dit pas qu'une pièce a été CUITE.
     */
    test("l'allègement entre dans la clé de partage", () => {
        expect(buildScene()).toContain("bakedParts: loaded");
    });

    /**
     * ⚠️ La retenue doit suivre la construction, jamais la précéder : une passe qui lève
     * n'a rien à léguer, et poser la carte avant l'appel la donnerait quand même.
     */
    test("elle retient APRÈS l'appel au moteur, pas avant", () => {
        const corps = buildScene();
        expect(corps.indexOf("this._sharedParts = sharedOut"))
            .toBeGreaterThan(corps.indexOf("const tree = build("));
    });

    /** La graine naît à `null` : la première construction n'a rien à emprunter. */
    test("la graine est déclarée au montage", () => {
        expect(SOURCE).toContain("this._sharedParts = null;");
    });
});
