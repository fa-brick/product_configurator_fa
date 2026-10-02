/**
 * LA PAGE CALÉE AU-DESSUS DU CLAVIER — D-389 (capture de Gerry, 2026-10-02) : sur téléphone,
 * le clavier numérique faisait glisser la page vers le haut, et la 3D sortait de l'écran.
 * La page se pose désormais sur la partie VISIBLE (`visualViewport`) pendant une saisie.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { KEYBOARD_MIN_HEIGHT, isTypingField, keyboardFit }
    from "@product_configurator_web_3d/configurator_state";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";

const SRC = join(__dirname, "..", "src", "page");
const SCSS = readFileSync(join(SRC, "configurator_page.scss"), "utf8").replace(/\/\*[\s\S]*?\*\//g, " ");
const XML = readFileSync(join(SRC, "configurator_page.xml"), "utf8").replace(/<!--[\s\S]*?-->/g, " ");

// Un téléphone de 412 × 915, clavier numérique ouvert : il reste ~ 480 px visibles.
const OPEN = { height: 480, offsetTop: 310, scale: 1 };
const base = { compact: true, framed: false, editing: true, innerHeight: 915, viewport: OPEN };

describe("keyboardFit — quand la page se cale, et où", () => {
    test("clavier ouvert pendant une saisie : la page prend la partie visible", () => {
        expect(keyboardFit(base)).toEqual({ top: 310, height: 480 });
    });

    test("les décimales du navigateur sont arrondies au pixel", () => {
        expect(keyboardFit({ ...base, viewport: { height: 480.6, offsetTop: 309.4, scale: 1 } }))
            .toEqual({ top: 309, height: 481 });
    });

    test("ⓘ les barres du navigateur qui se replient ne sont pas un clavier", () => {
        const bars = { height: 915 - KEYBOARD_MIN_HEIGHT + 1, offsetTop: 0, scale: 1 };
        expect(keyboardFit({ ...base, viewport: bars })).toBe(null);
    });

    test("pas de calage hors saisie, hors mode compact, ni dans un dialogue", () => {
        expect(keyboardFit({ ...base, editing: false })).toBe(null);
        expect(keyboardFit({ ...base, compact: false })).toBe(null);
        expect(keyboardFit({ ...base, framed: true })).toBe(null);
    });

    test("⚠️ un ZOOM au pincement réduit aussi la partie visible : ce n'est pas un clavier", () => {
        expect(keyboardFit({ ...base, viewport: { ...OPEN, scale: 2 } })).toBe(null);
    });

    test("sans `visualViewport` (navigateur ancien), la page garde sa place", () => {
        expect(keyboardFit({ ...base, viewport: null })).toBe(null);
    });
});

describe("isTypingField — ce qui appelle le clavier", () => {
    const input = (type) => ({ tagName: "INPUT", type });
    test("texte, nombre, recherche, zone de texte : oui", () => {
        for (const type of ["text", "number", "search", "tel", ""]) expect(isTypingField(input(type))).toBe(true);
        expect(isTypingField({ tagName: "TEXTAREA" })).toBe(true);
    });
    test("case, bouton, liste, rien : non", () => {
        for (const type of ["checkbox", "radio", "button", "range"]) expect(isTypingField(input(type))).toBe(false);
        expect(isTypingField({ tagName: "SELECT" })).toBe(false);
        expect(isTypingField({ tagName: "BUTTON" })).toBe(false);
        expect(isTypingField(null)).toBe(false);
    });
});

describe("la page suit le clavier", () => {
    let viewport, listeners, docListeners;
    beforeEach(() => {
        listeners = {};
        docListeners = {};
        viewport = { height: 915, offsetTop: 0, scale: 1,
                     addEventListener: (name, fn) => { listeners[name] = fn; } };
        global.window = { visualViewport: viewport, innerHeight: 915 };
        global.document = { activeElement: null,
                            addEventListener: (name, fn) => { docListeners[name] = fn; } };
    });
    afterEach(() => { delete global.window; delete global.document; });

    function makePage() {
        const field = { tagName: "INPUT", type: "text" };
        const el = { closest: () => null, contains: (node) => node === field };
        const page = Object.create(ConfiguratorPage.prototype);
        page.state = { compact: true, keyboard: null };
        page.pageRef = { el };
        page._watchKeyboard();
        return { page, field };
    }

    test("le clavier s'ouvre sur un champ de la page : la page se cale ; il se ferme : elle revient", () => {
        const { page, field } = makePage();
        document.activeElement = field;
        docListeners.focusin();
        expect(page.state.keyboard).toBe(null);               // clavier pas encore ouvert
        Object.assign(viewport, { height: 480, offsetTop: 310 });
        listeners.resize();
        expect(page.state.keyboard).toEqual({ top: 310, height: 480 });
        expect(page.keyboardStyle).toBe("--o-cfg3d-visible-top: 310px; --o-cfg3d-visible-height: 480px;");
        Object.assign(viewport, { offsetTop: 280 });           // le navigateur fait glisser
        listeners.scroll();
        expect(page.state.keyboard.top).toBe(280);
        Object.assign(viewport, { height: 915, offsetTop: 0 });
        listeners.resize();
        expect(page.state.keyboard).toBe(null);
        expect(page.keyboardStyle).toBe("");
    });

    test("un champ HORS de la page (la fiche dessous) ne la cale pas", () => {
        const { page } = makePage();
        document.activeElement = { tagName: "INPUT", type: "text" };
        Object.assign(viewport, { height: 480, offsetTop: 310 });
        listeners.resize();
        expect(page.state.keyboard).toBe(null);
    });

    test("⚠️ dans un dialogue (back-office), jamais", () => {
        const { page, field } = makePage();
        page.pageRef.el.closest = (sel) => (sel === ".modal" ? {} : null);
        document.activeElement = field;
        Object.assign(viewport, { height: 480, offsetTop: 310 });
        listeners.resize();
        expect(page.state.keyboard).toBe(null);
    });

    test("ⓘ sans `visualViewport`, rien n'est écouté", () => {
        global.window = { innerHeight: 915 };
        const page = Object.create(ConfiguratorPage.prototype);
        page.state = { compact: true, keyboard: null };
        page._watchKeyboard();
        expect(Object.keys(docListeners)).toEqual([]);
    });
});

describe("le gabarit et le style", () => {
    test("la racine porte la classe et le style du calage", () => {
        expect(XML).toMatch(/<div class="o_cfg3d_page" t-ref="page"\s+t-att-class="\{ 'o_cfg3d_page--keyboard': state\.keyboard \}"\s+t-att-style="keyboardStyle">/);
    });

    test("calée, la page est FIXE à la place et à la taille données ; la 3D cède, le titre aussi", () => {
        const block = SCSS.match(/\.o_cfg3d_page--keyboard \{([\s\S]*?)\n\}/);
        expect(block).not.toBe(null);
        expect(block[1]).toMatch(/position: fixed;/);
        expect(block[1]).toMatch(/top: var\(--o-cfg3d-visible-top, 0px\);/);
        expect(block[1]).toMatch(/height: var\(--o-cfg3d-visible-height, 100dvh\);/);
        expect(block[1]).toMatch(/\.o_cfg3d_viewer \{ min-height: 0; \}/);
        expect(block[1]).toMatch(/\.o_cfg3d_title \{ display: none; \}/);
    });
});
