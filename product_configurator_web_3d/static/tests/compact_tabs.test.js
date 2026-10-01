/**
 * LES ONGLETS DU MODE COMPACT — D-389 (Gerry, 2026-10-01) : « l'ensemble des attributs de
 * l'étape sélectionnable par un scroll horizontal. La sélection de question le centre en
 * largeur pour montrer qu'il y a des questions à gauche et à droite. Une fois la question
 * sélectionnée on affiche son champ en dessous. »
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { activeQuestionId, centerScrollLeft, layoutOn } from "@product_configurator_web_3d/configurator_state";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";

const SRC = join(__dirname, "..", "src", "page");
const XML = readFileSync(join(SRC, "configurator_page.xml"), "utf8").replace(/<!--[\s\S]*?-->/g, " ");
const SCSS = readFileSync(join(SRC, "configurator_page.scss"), "utf8").replace(/\/\*[\s\S]*?\*\//g, " ");

const q = (id, extra = {}) => ({ id, name: `Q${id}`, missing: false, answerLayout: "inline",
                                 displayType: "radio", values: [], ...extra });

describe("centrer l'onglet ouvert", () => {
    test("son milieu au milieu de la rangée", () => {
        // Rangée de 400 px, contenu de 1 000 ; onglet de 100 px à 450 → milieu à 500.
        expect(centerScrollLeft(400, 1000, 450, 100)).toBe(300);
    });

    test("borné aux deux bouts : le premier et le dernier touchent le bord", () => {
        expect(centerScrollLeft(400, 1000, 10, 100)).toBe(0);
        expect(centerScrollLeft(400, 1000, 900, 100)).toBe(600);
    });

    test("une rangée qui tient dans la vue ne défile pas", () => {
        expect(centerScrollLeft(400, 300, 200, 100)).toBe(0);
    });
});

describe("l'onglet ouvert", () => {
    const QUESTIONS = [q(1), q(2, { missing: true }), q(3)];

    test("celui qu'on a choisi, tant qu'il est servi", () => {
        expect(activeQuestionId(QUESTIONS, 3)).toBe(3);
    });

    test("sinon la première question qui MANQUE — c'est là qu'il y a à faire", () => {
        expect(activeQuestionId(QUESTIONS, null)).toBe(2);
        // ⓘ Une réponse a masqué la question ouverte : on ne reste pas sur une absente.
        expect(activeQuestionId(QUESTIONS, 99)).toBe(2);
    });

    test("sinon la première ; aucune sans question", () => {
        expect(activeQuestionId([q(1), q(3)], null)).toBe(1);
        expect(activeQuestionId([], 1)).toBe(null);
    });
});

describe("une grille devient une rangée en mode compact (Q3)", () => {
    test("cartes et grandes pastilles, `inline` comme `line` : la liste complète défile", () => {
        for (const displayType of ["card", "swatch"]) {
            for (const answerLayout of ["inline", "line"]) {
                expect(layoutOn(q(1, { displayType, answerLayout }), true)).toBe("scroll");
            }
        }
    });

    test("`summary` reste un résumé, et une forme sans image garde la sienne", () => {
        expect(layoutOn(q(1, { displayType: "card", answerLayout: "summary" }), true)).toBe("summary");
        expect(layoutOn(q(1, { displayType: "radio", answerLayout: "inline" }), true)).toBe("inline");
    });

    test("ⓘ sur ordinateur, rien ne change", () => {
        expect(layoutOn(q(1, { displayType: "card", answerLayout: "inline" }), false)).toBe("inline");
        expect(layoutOn(q(1, { displayType: "card", answerLayout: "line" }), false)).toBe("line");
    });
});

/** Une page sans montage : l'état, et les getters dont dépendent les onglets. */
function makePage({ shown = [], placement = null, compact = true } = {}) {
    const page = Object.create(ConfiguratorPage.prototype);
    page.state = { compact, question: null, reason: "x", step: null, panel: null,
                   selection: { nodeId: placement ? "n1" : null, isolated: false } };
    Object.defineProperty(page, "selectedPlacement", { value: placement });
    Object.defineProperty(page, "shownQuestions", { value: shown });
    page.views = [];
    // ⓘ La vue d'un onglet part APRÈS le rendu (D-389) : c'est ce chemin qu'on intercepte.
    page._showQuestionViewAfterPaint = (id) => page.views.push(id);
    return page;
}

describe("la page et ses onglets", () => {
    test("les questions de l'étape — ou celles de la pièce sélectionnée (D-333)", () => {
        expect(makePage({ shown: [q(1), q(2)] }).tabQuestions.map((x) => x.id)).toEqual([1, 2]);
        const placement = { questions: [q(7)] };
        expect(makePage({ shown: [q(1)], placement }).tabQuestions.map((x) => x.id)).toEqual([7]);
    });

    test("ouvrir un onglet : la question, et SA VUE (D-387) — pas pour une pièce", () => {
        const page = makePage({ shown: [q(1), q(2)] });
        page.onTab(q(2));
        expect(page.state.question).toBe(2);
        expect(page.activeQuestion.id).toBe(2);
        expect(page.state.reason).toBe(null);
        expect(page.views).toEqual([2]);
        const piece = makePage({ placement: { questions: [q(7)] } });
        piece.onTab(q(7));
        expect(piece.views).toEqual([]);
    });

    test("centrer seulement quand l'onglet CHANGE : immédiat la première fois, glissé ensuite", () => {
        const page = makePage();
        const calls = [];
        const row = {
            dataset: { active: "1" }, clientWidth: 400, scrollWidth: 1000,
            querySelector: () => ({ offsetLeft: 450, offsetWidth: 100 }),
            scrollTo: (opts) => calls.push(opts),
        };
        page.tabsRef = { el: row };
        page._settleTabs();
        expect(calls).toEqual([{ left: 300, behavior: "auto" }]);
        // Un rendu de plus (le prix, le bus) : la rangée n'est pas reprise à qui la fait défiler.
        page._settleTabs();
        expect(calls).toHaveLength(1);
        row.dataset.active = "2";
        page._settleTabs();
        expect(calls[1]).toEqual({ left: 300, behavior: "smooth" });
    });
});

describe("une réponse manquante ouvre SON onglet (D-385 + D-389)", () => {
    test("le toast nomme la question, et l'onglet s'ouvre sur elle", () => {
        const page = makePage({ shown: [q(1), q(2, { missing: true })] });
        page.state.model = { steps: [] };
        const toasts = [];
        page.notification = { add: (text) => toasts.push(text) };
        page.answersRef = { el: null };
        page._revealMissing([q(2, { missing: true, stepId: null })]);
        expect(toasts).toEqual(["Q2"]);
        expect(page.state.question).toBe(2);
    });
});

describe("le gabarit : les onglets en mode compact, la colonne d'avant sinon", () => {
    test("les questions de la colonne ne se rendent PAS en mode compact", () => {
        expect(XML).toContain('<section t-if="selectedPlacement and !state.compact" class="o_cfg3d_piece">');
        expect(XML).toContain('<t t-if="!selectedPlacement and !state.compact">');
    });

    test("les onglets, puis la boîte du champ : la question ouverte et la raison d'un refus", () => {
        const start = XML.indexOf('<t t-if="state.compact and activeQuestion">');
        expect(start).toBeGreaterThan(-1);
        const block = XML.slice(start, XML.indexOf('<p t-if="!questions.length', start));
        expect(block).toContain('t-foreach="tabQuestions"');
        expect(block).toContain('t-on-click="() => this.onTab(tab)"');
        expect(block).toContain('t-att-aria-selected=');
        expect(block).toContain('<span t-if="tab.missing" class="o_cfg3d_tab_missing"');
        const field = block.slice(block.indexOf('<div class="o_cfg3d_field" role="tabpanel">'));
        expect(field).toContain('<t t-set="question" t-value="activeQuestion"/>');
        expect(field).toContain('t-call="product_configurator_web_3d.Question"');
        expect(field).toContain('<p t-if="state.reason" class="o_cfg3d_reason"');
        // ⓘ Et la raison de la colonne se tait : jamais deux fois le même refus.
        expect(XML).toContain('<p t-if="state.reason and !state.compact" class="o_cfg3d_reason"');
    });

    test("la boîte du champ prend la hauteur de SON CONTENU, bornée — pas de blanc dessous", () => {
        // ⓘ D'abord fixe (172 px) : une ligne résumé y laissait 100 px vides (Gerry, 2026-10-01).
        const field = SCSS.slice(SCSS.indexOf(".o_cfg3d_field {"), SCSS.indexOf("}", SCSS.indexOf(".o_cfg3d_field {")));
        expect(field).not.toMatch(/(^|\s)height:/);
        expect(field).toMatch(/max-height: 40vh;\s*max-height: 40dvh;\s*overflow-y: auto;/);
        expect(SCSS).toMatch(/@media \(max-width: \$o-cfg3d-compact-max\) \{\s*flex: 0 0 auto;/);
    });
});
