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

describe("la zone réservée en haut du viewer (D-389)", () => {
    const { viewInset, VIEW_INSET_GAP } = require("@product_configurator_web_3d/configurator_state");

    test("le bas de ce qui recouvre le viewer, plus un peu d'air ; rien = 0", () => {
        expect(viewInset(96)).toBe(96 + VIEW_INSET_GAP);
        expect(viewInset(95.6)).toBe(Math.round(95.6 + VIEW_INSET_GAP));
        expect(viewInset(0)).toBe(0);
    });

    test("la page la MESURE et la passe au viewer", () => {
        const XML = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.xml"), "utf8");
        expect(XML).toContain('viewInsetTop="state.viewInsetTop"');
        const JS = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");
        const after = JS.slice(JS.indexOf("    _afterRender() {"), JS.indexOf("    _afterRender() {") + 300);
        expect(after).toContain("this._measureViewInset();");
    });

    test("seuls comptent les éléments qui RECOUVRENT le viewer, et l'écriture n'a lieu que si ça change", () => {
        const rect = (left, top, width, height) => ({ left, top, right: left + width, bottom: top + height, height });
        const viewer = { getBoundingClientRect: () => rect(0, 0, 1060, 900) };
        const chip = { getBoundingClientRect: () => rect(430, 12, 80, 28) };
        const close = { getBoundingClientRect: () => rect(1352, 12, 32, 22) };   // au-dessus de la colonne
        const page = Object.create(ConfiguratorPage.prototype);
        let writes = 0;
        const state = { _v: 0 };
        Object.defineProperty(state, "viewInsetTop", { get: () => state._v, set: (v) => { writes++; state._v = v; } });
        page.state = state;
        page.pageRef = { el: {
            querySelector: () => viewer,
            querySelectorAll: () => [chip, close],
        } };
        page._measureViewInset();
        expect(page.state.viewInsetTop).toBe(40 + VIEW_INSET_GAP);
        page._measureViewInset();
        expect(writes).toBe(1);
    });
});
