/**
 * LE MODE COMPACT — D-389 (Gerry, 2026-10-01) : sur téléphone, la page rend autre chose
 * (onglets, barre en haut, tape qui ferme le panneau). Le SCSS dispose la page, le JS décide
 * de ce qu'il rend : ils doivent lire le MÊME seuil.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { browser } from "@web/core/browser/browser";
import { COMPACT_MAX_WIDTH, COMPACT_QUERY } from "@product_configurator_web_3d/configurator_state";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";

const SCSS = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.scss"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ");

describe("un seul seuil pour le SCSS et le JS", () => {
    test("la variable du SCSS vaut le seuil du JS", () => {
        const declared = SCSS.match(/\$o-cfg3d-compact-max:\s*(\d+)px;/);
        expect(declared).not.toBe(null);
        expect(Number(declared[1])).toBe(COMPACT_MAX_WIDTH);
        expect(COMPACT_QUERY).toBe(`(max-width: ${COMPACT_MAX_WIDTH}px)`);
    });

    test("⚠️ aucune media query de largeur n'écrit son nombre en dur", () => {
        // Un 900px recopié survivrait au changement de la variable, et la bande entre les
        // deux serait disposée pour le téléphone et rendue pour l'ordinateur.
        expect(SCSS).not.toMatch(/@media[^{]*(max|min)-width:\s*\d/);
        expect(SCSS).toMatch(/@media \(max-width: \$o-cfg3d-compact-max\)/);
    });
});

describe("la page suit la largeur de la fenêtre", () => {
    function fakeQuery(matches) {
        const listeners = [];
        return {
            matches,
            addEventListener: (name, fn) => name === "change" && listeners.push(fn),
            fire: (value) => listeners.forEach((fn) => fn({ matches: value })),
        };
    }

    afterEach(() => { delete browser.matchMedia; });

    test("lue AVANT le premier rendu, puis suivie", () => {
        const query = fakeQuery(true);
        browser.matchMedia = (text) => (text === COMPACT_QUERY ? query : null);
        const page = Object.create(ConfiguratorPage.prototype);
        page.state = { compact: false };
        page._watchCompact();
        expect(page.state.compact).toBe(true);
        query.fire(false);
        expect(page.state.compact).toBe(false);
        query.fire(true);
        expect(page.state.compact).toBe(true);
    });

    test("ⓘ sans `matchMedia`, la page reste celle de l'ordinateur", () => {
        const page = Object.create(ConfiguratorPage.prototype);
        page.state = { compact: false };
        page._watchCompact();
        expect(page.state.compact).toBe(false);
    });
});
