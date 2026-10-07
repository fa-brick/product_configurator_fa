/**
 * LE PANNEAU DE CHOIX SUR TÉLÉPHONE — D-389 (Gerry, 2026-10-01, capture Roomle) : « pour
 * permettre de voir les modifications de sélection, la liste ne remonte pas jusqu'en haut. Un
 * clic dans le viewer 3D la retire. » Q4 : la tape FERME SEULEMENT ; Q5 : pas sur ordinateur.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";

const SRC = join(__dirname, "..", "src", "page");
const XML = readFileSync(join(SRC, "configurator_page.xml"), "utf8").replace(/<!--[\s\S]*?-->/g, " ");
const SCSS = readFileSync(join(SRC, "configurator_page.scss"), "utf8").replace(/\/\*[\s\S]*?\*\//g, " ");

/** Une page sans montage, un panneau ouvert ou non, et les sélections qu'elle aurait faites. */
function makePage({ compact, panel }) {
    const page = Object.create(ConfiguratorPage.prototype);
    page.state = { compact, panel: panel ? { questionId: 1 } : null, reason: "x",
                   selection: { nodeId: null, isolated: false } };
    Object.defineProperty(page, "selectableNodeIds", { value: new Set(["n1"]) });
    page.selected = [];
    page._select = (nodeId, isolated) => page.selected.push([nodeId, isolated]);
    return page;
}

describe("une tape dans la 3D, panneau ouvert", () => {
    test("sur téléphone : elle ferme le panneau, et ne sélectionne RIEN (Q4)", () => {
        const page = makePage({ compact: true, panel: true });
        page.onSelectPiece("n1");
        expect(page.state.panel).toBe(null);
        expect(page.selected).toEqual([]);
        // La tape suivante désigne.
        page.onSelectPiece("n1");
        expect(page.selected).toEqual([["n1", false]]);
    });

    test("une tape dans le VIDE ferme aussi — c'est le geste le plus fréquent", () => {
        const page = makePage({ compact: true, panel: true });
        page.onSelectPiece(null);
        expect(page.state.panel).toBe(null);
        expect(page.selected).toEqual([]);
    });

    test("le double clic aussi ne fait que fermer", () => {
        const page = makePage({ compact: true, panel: true });
        page.onActivatePiece("n1");
        expect(page.state.panel).toBe(null);
        expect(page.selected).toEqual([]);
    });

    test("ⓘ sur ordinateur, rien ne change (Q5) : le clic désigne, comme avant", () => {
        const page = makePage({ compact: false, panel: true });
        page.onSelectPiece("n1");
        expect(page.selected).toEqual([["n1", false]]);
        expect(page.state.panel).not.toBe(null);
    });

    test("sans panneau ouvert, la tape désigne", () => {
        const page = makePage({ compact: true, panel: false });
        page.onSelectPiece("n1");
        expect(page.selected).toEqual([["n1", false]]);
    });
});

describe("la liste ne remonte pas jusqu'en haut", () => {
    test("la colonne GRANDIT le temps du panneau — elle porte la marque", () => {
        expect(XML).toContain(`<aside class="o_cfg3d_side" t-att-class="{ 'o_cfg3d_side--panel': panelQuestion }">`);
    });

    // ⚠️ En % de la PAGE et non de l'écran (L-532) : dans le dialogue du back-office, la page
    // n'est pas l'écran, et 58dvh + 30vh débordaient d'une page de 70vh.
    test("sur téléphone, à 58 % de la page, et la 3D peut descendre sous 45 %", () => {
        expect(SCSS).toMatch(/&\.o_cfg3d_side--panel \{\s*(\/\*[\s\S]*?\*\/\s*)?flex-basis: 58%;\s*\}/);
        const viewer = SCSS.slice(SCSS.indexOf(".o_cfg3d_viewer {"), SCSS.indexOf(".o_cfg3d_side {"));
        expect(viewer).toMatch(/@media \(max-width: \$o-cfg3d-compact-max\) \{\s*min-height: 30%;/);
        // 58 + 30 tiennent dans la page ; avec 45 %, elle aurait débordé.
        expect(58 + 30).toBeLessThanOrEqual(100);
    });

    test("dans un dialogue plein écran, la page remplit le corps au lieu de 70vh (L-532)", () => {
        const read = (p) => readFileSync(join(__dirname, "../src", p), "utf8");
        for (const host of ["configurator_dialog.scss", "page/configurator_action.scss"]) {
            const scss = read(host);
            const full = scss.slice(scss.indexOf("@include media-breakpoint-down(sm)"));
            expect(full).toContain(".o_modal_full");
            expect(full).toMatch(/\.o_cfg3d_page \{ height: 100%; \}/);
            expect(full).toMatch(/overflow: hidden;/);
        }
    });

    test("la poignée ferme, sur téléphone seulement", () => {
        const panel = XML.slice(XML.indexOf('<t t-name="product_configurator_web_3d.AnswerPanel">'));
        expect(panel).toMatch(/<button t-if="state.compact" type="button" class="o_cfg3d_panel_grip"[\s\S]*?t-on-click="\(\) => this.closePanel\(\)">\s*<i class="oi oi-chevron-down" role="img"\/>/);
    });
});

describe("l'en-tête du panneau : la flèche, puis le nom, sur une ligne (Gerry, 2026-10-01)", () => {
    test("la flèche est le retour, DANS le titre ; « Retour » ne vit plus que dans son nom", () => {
        const panel = XML.slice(XML.indexOf('<t t-name="product_configurator_web_3d.AnswerPanel">'));
        const head = panel.slice(panel.indexOf('<header class="o_cfg3d_panel_head">'), panel.indexOf("</header>"));
        expect(head).toMatch(/<h2 class="o_cfg3d_panel_title">\s*<button type="button" class="o_cfg3d_panel_back"/);
        expect(head).toContain('t-att-aria-label="backLabel"');
        expect(head).toContain('<i class="oi oi-arrow-left" role="img"/>');
        expect(head).toContain('<span t-esc="question.name"/>');
        expect(head).not.toContain('t-esc="backLabel"');
        expect(SCSS).toMatch(/\.o_cfg3d_panel_title \{\s*display: flex;\s*align-items: center;/);
    });
});
