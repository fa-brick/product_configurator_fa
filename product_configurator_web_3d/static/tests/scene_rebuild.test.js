/** @odoo-module */
/**
 * scene_rebuild.test.js — la page CONSTRUIT par la session, et ne rejoue aucun réglage.
 *
 * ⚠️ **Une graine absente ne lève pas, ne se voit pas, et ne se mesure qu'au
 * chronomètre.** `build()` reparti sans rien refait l'arbre ENTIER — booléens compris —
 * pour une seule pose neuve. Mesuré le 2026-09-22 sur le JeNo, au travers du serveur
 * d'essai : **2 742 ms sans graine, 1 616 ms avec**, les douze autres pièces annoncées
 * « semée » à 0 ms. L'écran, lui, est identique dans les deux cas : rien ne dit qu'on paie.
 *
 * La graine avait été posée ICI, chez l'appelant — et c'est la faute que D-329 ferme :
 * une règle posée chez les appelants est une règle que les appelants suivants n'auront pas
 * ([[L-270]]). Elle vit désormais dans la session de construction du moteur, et cette page
 * n'a plus le droit de la rejouer, ni de décider du chargement de la CSG, ni de projeter.
 *
 * ⓘ On éprouve la SOURCE, comme `viewer_props.test.js` — l'éditeur n'est pas dans ce
 * dépôt (son moteur y est un bouchon), et ce qui doit tenir est le contrat de l'appel.
 * Les commentaires sont retirés avant de chercher : une garde qui lit le texte brut
 * trouve l'interdit dans la phrase qui le proscrit ([[L-352]]).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const RAW = readFileSync(
    join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");
const SOURCE = RAW.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ");

/** Le corps de `_buildScene`, depuis son entête jusqu'au `catch`. */
function buildScene() {
    const start = SOURCE.indexOf("async _buildScene(");
    expect(start).toBeGreaterThan(-1);
    const end = SOURCE.indexOf("} catch (e) {", start);
    expect(end).toBeGreaterThan(start);
    return SOURCE.slice(start, end);
}

describe("la scène se construit par la SESSION du moteur (D-329)", () => {
    test("la session est créée au montage, avec les deux chargeurs", () => {
        expect(SOURCE).toContain("this._session = createBuildSession({ getThree, getCSG })");
    });

    test("elle PRÉPARE (THREE, et la CSG si la recette le demande) avant de construire", () => {
        const corps = buildScene();
        expect(corps).toContain("await this._session.prepare(buildable)");
        expect(corps.indexOf("this._session.prepare("))
            .toBeLessThan(corps.indexOf("this._session.build("));
    });

    test("les fichiers cuits sont lus AVANT la construction, et entrent dans la session", () => {
        // `build()` est synchrone ; un fichier se lit en asynchrone. Et c'est par cette
        // table que l'allègement entre dans la clé de partage.
        const corps = buildScene();
        expect(corps.indexOf("await this._loadBaked(baked)"))
            .toBeLessThan(corps.indexOf("this._session.build("));
        expect(corps).toContain("{ bakedParts, importedGeometries, chronicle }");
    });

    test("⚠️ les fichiers IMPORTÉS aussi — sans eux, une pièce de fichier est un volume vide", () => {
        // La page ne les lisait pas du tout : les inserts du JeNo y manquaient (2026-09-24).
        const corps = buildScene();
        expect(corps.indexOf("await this._loadImported(buildable, imported)"))
            .toBeLessThan(corps.indexOf("this._session.build("));
    });

    test("les QUATRE projections viennent de la session — aucune n'est refaite ici", () => {
        const corps = buildScene();
        expect(corps).toContain("const { worlds, solids, baked: bakedSolids, pieces, postBuild } =");
        expect(corps).toContain("this._bakedSolids = bakedSolids");
        expect(corps).toContain("this.state.postBuild = postBuild");
    });
});

describe("⚠️ ce que la page N'A PLUS le droit de faire", () => {
    test("appeler le moteur en direct", () => {
        expect(SOURCE).not.toMatch(/from "@product_editor\/engine\/builder\/build"/);
        expect(SOURCE).not.toMatch(/(?<![.\w])build\(\s*buildable/);   // pas `session.build(`
        expect(SOURCE).not.toMatch(/from "@product_editor\/engine\/builder\/part_descriptor"/);
    });

    test("décider du chargement de la CSG — le prédicat avait déjà divergé une fois", () => {
        expect(SOURCE).not.toContain("_hasBoolean");
        expect(SOURCE).not.toMatch(/\bgetCSG\(\)/);
        expect(SOURCE).not.toContain("booleanModeOf");
    });

    test("tenir la graine elle-même", () => {
        expect(SOURCE).not.toContain("sharedSeed");
        expect(SOURCE).not.toContain("_sharedParts");
    });

    test("lire un fichier cuit avec SON lecteur — c'est celui de l'éditeur qui sert", () => {
        expect(SOURCE).not.toContain("page/baked_parts");
        expect(SOURCE).toContain("bakedSolidsFromScene(this._session.THREE");
    });

    test("projeter l'arbre elle-même", () => {
        for (const guichet of ["worldByNodeId(", "solidsByNodeId(", "projectAssemblyPieces("]) {
            expect(SOURCE).not.toContain(guichet);
        }
    });
});
