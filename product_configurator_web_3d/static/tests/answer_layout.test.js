/**
 * LA DISPOSITION des réponses — D-382, lot 2 : la rangée qui DÉFILE (`scroll`).
 * Logique pure éprouvée directement ; gabarit et feuille de style lus dans les sources,
 * commentaires retirés ([[L-352]]) — Jest n'a ni bundle ni OWL.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { toViewModel, answerLayoutOf, revealScrollLeft, rowEdges }
    from "@product_configurator_web_3d/configurator_state";

const SRC = join(__dirname, "..", "src");
const XML = readFileSync(join(SRC, "page", "configurator_page.xml"), "utf8")
    .replace(/<!--[\s\S]*?-->/g, " ");
const SCSS = readFileSync(join(SRC, "page", "configurator_page.scss"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ");
const JS = readFileSync(join(SRC, "page", "configurator_page.js"), "utf8");

describe("la disposition effective — le miroir de `_web_answer_layout`", () => {
    const of = (displayType, answerLayout) => answerLayoutOf({ displayType, answerLayout });

    test("défilement et ligne : cartes et grandes pastilles seulement", () => {
        for (const layout of ["scroll", "line"]) {
            expect(of("card", layout)).toBe(layout);
            expect(of("swatch", layout)).toBe(layout);
            for (const form of ["radio", "pills", "select", "color", "multi"]) {
                expect(of(form, layout)).toBe("inline");
            }
        }
    });

    test("le résumé : aussi les boutons et la liste (Gerry), jamais la couleur ni les cases", () => {
        for (const form of ["card", "swatch", "radio", "pills", "select"]) {
            expect(of(form, "summary")).toBe("summary");
        }
        expect(of("color", "summary")).toBe("inline");
        expect(of("multi", "summary")).toBe("inline");
    });

    test("⚠️ absente ou inconnue : `inline`, l'affichage d'avant", () => {
        expect(of("card", undefined)).toBe("inline");
        expect(of("card", "carousel")).toBe("inline");
        // Une question sans forme déclarée est un `radio` — le repli de `toQuestion`.
        expect(answerLayoutOf({ answerLayout: "summary" })).toBe("summary");
        const line = { id: 1, name: "Plaque", displayType: "card", values: [] };
        expect(toViewModel({ attributes: [line] }).questions[0].answerLayout).toBe("inline");
        expect(toViewModel({ attributes: [{ ...line, answerLayout: "scroll" }] })
            .questions[0].answerLayout).toBe("scroll");
    });
});

describe("ramener le choix à l'écran", () => {
    // Une rangée de 300 px de large, cartes de 80 px.
    test("visible en entier : on ne touche à rien", () => {
        expect(revealScrollLeft(0, 300, 88, 80)).toBeNull();
        expect(revealScrollLeft(100, 300, 120, 80)).toBeNull();
    });

    test("coupé à droite : il vient au bord droit", () => {
        expect(revealScrollLeft(0, 300, 264, 80)).toBe(44);
    });

    test("coupé à gauche : il vient au bord gauche", () => {
        expect(revealScrollLeft(200, 300, 176, 80)).toBe(176);
    });
});

describe("le gabarit — une enveloppe autour des deux grilles à image", () => {
    const branch = (form, next) => XML.slice(XML.indexOf(`question.displayType === '${form}'`),
                                             XML.indexOf(next));
    const BRANCHES = [
        ["card", "question.displayType === 'swatch'", "o_cfg3d_cards"],
        ["swatch", "question.displayType === 'color'", "o_cfg3d_bigswatches"],
    ];

    test("la carte et la grande pastille : l'enveloppe, activée par la disposition", () => {
        for (const [form, next, grid] of BRANCHES) {
            const bloc = branch(form, next);
            expect(bloc).toContain("'o_cfg3d_scrollrow--active': question.answerLayout === 'scroll'");
            expect(bloc).toContain('t-att-data-chosen="this.chosenKey(question)"');
            expect(bloc).toContain('t-on-scroll.capture="onRowScroll"');
            // La grille est le PREMIER enfant de l'enveloppe : la page la lit ainsi.
            expect(bloc).toMatch(new RegExp(`t-on-mouseenter="onRowScroll">\\s*<div class="${grid}"`));
            expect(bloc).toContain(
                `<t t-if="question.answerLayout === 'scroll'" t-call="product_configurator_web_3d.ScrollArrows"/>`);
        }
    });

    test("⚠️ AUCUN composant à emplacement dans une question — il y voyait la DERNIÈRE ([[L-453]])", () => {
        // Le gabarit `Question` est appelé par `t-call` depuis une boucle ; un slot n'y
        // recopie pas son contexte, et toutes les questions rendaient la même liste.
        const question = XML.slice(XML.indexOf('t-name="product_configurator_web_3d.Question"'),
                                   XML.indexOf('t-name="product_configurator_web_3d.ScrollArrows"'));
        expect(question).not.toMatch(/<[A-Z][A-Za-z]*[^>]*>\s*<div class="o_cfg3d_(cards|bigswatches)"/);
        expect(JS).not.toMatch(/class ScrollRow/);
    });

    test("les flèches avancent et reculent la rangée", () => {
        const arrows = XML.slice(XML.indexOf('t-name="product_configurator_web_3d.ScrollArrows"'));
        expect(arrows).toContain('t-on-click="(ev) => this.onRowArrow(ev, -1)"');
        expect(arrows).toContain('t-on-click="(ev) => this.onRowArrow(ev, 1)"');
    });

    test("une seule définition de chaque méthode de rangée ([[L-361]])", () => {
        for (const name of ["chosenKey", "_settleRows", "_markEdges", "onRowScroll", "onRowArrow"]) {
            expect(JS.match(new RegExp(`^ {4}${name}\\(`, "gm"))).toHaveLength(1);
        }
    });

    test("⚠️ la rangée ne ramène le choix que lorsqu'il CHANGE — pas à chaque rendu", () => {
        const settle = JS.slice(JS.indexOf("    _settleRows() {"), JS.indexOf("    _markEdges("));
        expect(settle).toMatch(/if \(row\.dataset\.chosen !== row\.dataset\.shown\) \{\s*row\.dataset\.shown = row\.dataset\.chosen;/);
        const setup = JS.slice(JS.indexOf("export class ConfiguratorPage"));
        expect(setup).toContain("onMounted(() => this._settleRows());");
        expect(setup).toContain("onPatched(() => this._settleRows());");
    });
});

describe("les bords d'une rangée", () => {
    test("au début, au milieu, à la fin — au pixel près", () => {
        expect(rowEdges(0, 300, 900)).toEqual({ start: true, end: false });
        expect(rowEdges(300, 300, 900)).toEqual({ start: false, end: false });
        expect(rowEdges(599.5, 300, 900)).toEqual({ start: false, end: true });
        expect(rowEdges(0, 300, 300)).toEqual({ start: true, end: true });
    });
});

describe("la feuille de style de la rangée", () => {
    const row = SCSS.slice(SCSS.indexOf(".o_cfg3d_scrollrow--active {"), SCSS.indexOf(".o_cfg3d_scrollrow_arrow {"));

    test("une seule rangée, qui défile, s'aimante, et positionnée pour `offsetLeft`", () => {
        for (const decl of ["position: relative;", "grid-template-columns: none;",
                            "grid-auto-flow: column;", "overflow-x: auto;",
                            "scroll-snap-type: x mandatory;"]) {
            expect(row).toContain(decl);
        }
    });

    test("chaque taille montre n réponses ENTIÈRES et une moitié — 4, 3 et 2 cartes", () => {
        const expected = { "": 3, "--small": 4, "--large": 2 };
        for (const grid of ["o_cfg3d_cards", "o_cfg3d_bigswatches"]) {
            for (const [suffix, n] of Object.entries(expected)) {
                const m = row.match(new RegExp(
                    `> \\.${grid}${suffix} \\{ grid-auto-columns: #\\{"calc\\(\\(100% - (\\d+)px\\) / ([\\d.]+)\\)"\\}; \\}`));
                expect(m).not.toBeNull();
                // n écarts de 8 px, n + 0,5 colonnes.
                expect(Number(m[1])).toBe(n * 8);
                expect(Number(m[2])).toBe(n + 0.5);
            }
        }
    });

    test("⚠️ la colonne des questions ne s'élargit pas à la longueur d'une rangée", () => {
        // Sans `min-width: 0`, un élément flexible garde la largeur de son contenu : quinze
        // teintes en rangée portaient la colonne de 340 à 1 080 px.
        const side = SCSS.slice(SCSS.indexOf(".o_cfg3d_side {"), SCSS.indexOf(".o_cfg3d_scroll {"));
        expect(side).toContain("flex: 0 0 340px;");
        expect(side).toMatch(/min-width: 0;/);
    });

    test("⚠️ le `calc()` est INTERPOLÉ — libsass ne doit pas l'évaluer ([[L-302]])", () => {
        expect(row).not.toMatch(/grid-auto-columns: calc/);
    });

    test("les flèches ne paraissent qu'à la souris, et pas au bord atteint", () => {
        const hover = SCSS.slice(SCSS.indexOf("@media (hover: hover)"));
        expect(hover).toContain(".o_cfg3d_scrollrow:hover .o_cfg3d_scrollrow_arrow { display: flex; }");
        expect(hover).toMatch(/\.o_cfg3d_scrollrow--start:hover \.o_cfg3d_scrollrow_arrow--prev,\s*\.o_cfg3d_scrollrow--end:hover \.o_cfg3d_scrollrow_arrow--next \{ display: none; \}/);
    });
});
