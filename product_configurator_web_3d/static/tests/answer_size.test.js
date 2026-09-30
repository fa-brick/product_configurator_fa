/**
 * LA TAILLE d'une carte ou d'une grande pastille — D-382 (Gerry, 2026-09-30 : « plutôt modifier
 * la taille que le nombre en largeur »). Gardes de gabarit lues dans les sources, comme leurs
 * voisines : Jest n'a ni bundle ni OWL. Les commentaires sont retirés avant de chercher
 * ([[L-352]]) — la prose de ces fichiers cite les classes qu'elle explique.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { toViewModel, ANSWER_SIZES } from "@product_configurator_web_3d/configurator_state";

const SRC = join(__dirname, "..", "src");
const XML = readFileSync(join(SRC, "page", "configurator_page.xml"), "utf8")
    .replace(/<!--[\s\S]*?-->/g, " ");
const SCSS = readFileSync(join(SRC, "page", "configurator_page.scss"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ");

/** Le corps d'une règle SCSS de premier niveau, accolades imbriquées comprises. */
function rule(selector) {
    const start = SCSS.indexOf(`${selector} {`);
    if (start < 0) return "";
    let depth = 0;
    for (let i = SCSS.indexOf("{", start); i < SCSS.length; i++) {
        if (SCSS[i] === "{") depth++;
        if (SCSS[i] === "}" && --depth === 0) return SCSS.slice(start, i + 1);
    }
    return "";
}

describe("la taille servie à la page", () => {
    const line = { id: 1, name: "Plaque", displayType: "card", values: [] };
    const sizeOf = (extra) => toViewModel({ attributes: [{ ...line, ...extra }] }).questions[0].answerSize;

    test("les trois tailles passent telles quelles", () => {
        for (const size of ANSWER_SIZES) {
            expect(sizeOf({ answerSize: size })).toBe(size);
        }
    });

    test("⚠️ absente ou inconnue, c'est `medium` — l'affichage d'avant ce réglage", () => {
        // Un serveur qui ne la sert pas encore (8069 non redémarré) ne doit rien changer.
        expect(sizeOf({})).toBe("medium");
        expect(sizeOf({ answerSize: "huge" })).toBe("medium");
    });
});

describe("le gabarit porte la taille", () => {
    test("la carte : une classe par taille, sur la grille", () => {
        expect(XML).toContain("t-att-class=\"'o_cfg3d_cards--' + question.answerSize\"");
    });

    test("la grande pastille : la taille S'AJOUTE à la marque, sans la remplacer", () => {
        expect(XML).toContain(
            "t-att-class=\"'o_cfg3d_bigswatches--' + question.swatchMark + ' o_cfg3d_bigswatches--' + question.answerSize\"");
    });
});

describe("la feuille de style dessine chaque taille", () => {
    test("⚠️ `medium` reste la règle d'avant — un attribut existant ne bouge pas", () => {
        const cards = rule(".o_cfg3d_cards");
        expect(cards).toMatch(/^\.o_cfg3d_cards \{\s*display: grid;\s*grid-template-columns: repeat\(auto-fill, minmax\(96px, 1fr\)\);/);
        expect(rule(".o_cfg3d_bigswatches")).toContain("minmax(84px, 1fr)");
        expect(rule(".o_cfg3d_bigswatch_disc")).toMatch(/width: 64px;\s*height: 64px;/);
        // Aucune règle `--medium` : elle ne pourrait que diverger de la règle de base.
        expect(SCSS).not.toContain("--medium");
    });

    test("la carte : 64 px en petite (72 ne loge que trois cartes), 140 px en grande", () => {
        const cards = rule(".o_cfg3d_cards");
        expect(cards).toMatch(/&--small \{ grid-template-columns: repeat\(auto-fill, minmax\(64px, 1fr\)\); \}/);
        expect(cards).toMatch(/&--large \{ grid-template-columns: repeat\(auto-fill, minmax\(140px, 1fr\)\); \}/);
    });

    test("⚠️ chaque taille donne un nombre de cartes DIFFÉRENT dans la colonne de 340 px", () => {
        // 72 px rendait trois cartes, comme la moyenne : la petite taille ne changeait rien.
        // Largeur utile : 308 px, 293 px quand une barre de défilement classique s'y loge.
        const min = (cls) => Number(rule(".o_cfg3d_cards").match(
            new RegExp(`${cls} \\{ grid-template-columns: repeat\\(auto-fill, minmax\\((\\d+)px`))[1]);
        const fit = (width, size) => Math.floor((width + 8) / (size + 8));
        for (const width of [308, 293]) {
            expect(fit(width, min("&--small"))).toBe(4);
            expect(fit(width, min("&--large"))).toBe(2);
        }
        expect(fit(308, 96)).toBe(3);
    });

    test("la grande pastille : le disque ET sa case de grille suivent", () => {
        const grid = rule(".o_cfg3d_bigswatches");
        expect(grid).toContain("&--small { grid-template-columns: repeat(auto-fill, minmax(68px, 1fr)); }");
        expect(grid).toContain("&--large { grid-template-columns: repeat(auto-fill, minmax(108px, 1fr)); }");
        const disc = rule(".o_cfg3d_bigswatch_disc");
        expect(disc).toContain(".o_cfg3d_bigswatches--small & { width: 48px; height: 48px; }");
        expect(disc).toContain(".o_cfg3d_bigswatches--large & { width: 88px; height: 88px; }");
    });
});
