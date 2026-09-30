/**
 * LES ÉTAPES de la page — D-385 (Gerry, 2026-09-30) : « les étapes conditionnent ce qui est
 * vu dans la sidebar », en pastilles en haut du viewer ; l'étape suivante reste GRISÉE tant
 * qu'une question obligatoire manque ; un clic sur une pastille grisée dit ce qui manque et
 * y mène.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { toViewModel, activeStepId, stepQuestions, missingBefore, stepChips, questionView }
    from "@product_configurator_web_3d/configurator_state";

const SRC = join(__dirname, "..", "src");
const XML = readFileSync(join(SRC, "page", "configurator_page.xml"), "utf8")
    .replace(/<!--[\s\S]*?-->/g, " ");
const JS = readFileSync(join(SRC, "page", "configurator_page.js"), "utf8");

const STEPS = [{ id: 10, name: "Plaques" }, { id: 20, name: "Impressions" }, { id: 30, name: "Options" }];
const q = (id, stepId, missing = false) => ({ id, name: `Q${id}`, stepId, missing });

describe("l'état servi porte les étapes", () => {
    test("les étapes, leur vue, et l'étape de chaque question", () => {
        const model = toViewModel({
            attributes: [{ id: 1, name: "Couleur", stepId: 20, missing: true, values: [] }],
            steps: [{ id: 20, name: "Impressions", camera: { pose: { azimuth: 1 } } }],
        });
        expect(model.steps).toEqual([{ id: 20, name: "Impressions", camera: { pose: { azimuth: 1 } } }]);
        expect(model.questions[0].stepId).toBe(20);
        expect(model.questions[0].missing).toBe(true);
    });

    test("⚠️ un serveur qui ne sert pas encore les étapes : page à plat, rien ne manque", () => {
        const model = toViewModel({ attributes: [{ id: 1, name: "Couleur", values: [] }] });
        expect(model.steps).toEqual([]);
        expect(model.questions[0].stepId).toBe(null);
        expect(model.questions[0].missing).toBe(false);
    });

    test("ⓘ une étape SANS vue ne bouge pas la caméra (`camera: null`)", () => {
        expect(toViewModel({ steps: [{ id: 1, name: "A" }] }).steps[0].camera).toBe(null);
    });
});

describe("la colonne ne montre que l'étape affichée", () => {
    const QUESTIONS = [q(1, 10), q(2, 10), q(3, 20)];

    test("les questions de l'étape, et elles seules", () => {
        expect(stepQuestions(QUESTIONS, STEPS, 20).map((x) => x.id)).toEqual([3]);
    });

    test("sans étape, toutes — la page d'avant", () => {
        expect(stepQuestions(QUESTIONS, [], null)).toBe(QUESTIONS);
    });

    test("l'étape choisie tant qu'elle est servie, sinon la première", () => {
        expect(activeStepId(STEPS, 20)).toBe(20);
        expect(activeStepId(STEPS, null)).toBe(10);
        // ⓘ Une réponse a masqué l'étape où l'on était : on retombe sur la première.
        expect(activeStepId(STEPS, 99)).toBe(10);
        expect(activeStepId([], 20)).toBe(null);
    });
});

describe("une étape reste grisée tant qu'une obligatoire manque AVANT elle", () => {
    test("il manque une réponse en 1 : 2 et 3 sont grisées, 1 ne l'est pas", () => {
        const chips = stepChips(STEPS, [q(1, 10, true), q(3, 20)], 10);
        expect(chips.map((c) => c.locked)).toEqual([false, true, true]);
        expect(chips.map((c) => c.active)).toEqual([true, false, false]);
    });

    test("⚠️ une étape se mérite par TOUTES celles d'avant, pas seulement la précédente", () => {
        // Il manque en 1, et l'on regarde 2 : 3 reste grisée — sinon on sauterait 1.
        const chips = stepChips(STEPS, [q(1, 10, true), q(3, 20)], 20);
        expect(chips.map((c) => c.locked)).toEqual([false, false, true]);
    });

    test("ⓘ l'étape AFFICHÉE n'est jamais grisée — on doit pouvoir y répondre", () => {
        const chips = stepChips(STEPS, [q(1, 10, true)], 30);
        expect(chips[2]).toMatchObject({ active: true, locked: false });
    });

    test("tout est répondu : rien n'est grisé", () => {
        expect(stepChips(STEPS, [q(1, 10), q(3, 20)], 10).some((c) => c.locked)).toBe(false);
    });
});

describe("ce qui manque, dans l'ordre où on le trouvera", () => {
    const QUESTIONS = [q(5, 30, true), q(3, 20, true), q(1, 10, true), q(2, 10, true)];

    test("avant une étape : l'ordre des étapes, puis celui des questions", () => {
        expect(missingBefore(STEPS, QUESTIONS, 30).map((x) => x.id)).toEqual([1, 2, 3]);
        expect(missingBefore(STEPS, QUESTIONS, 10)).toEqual([]);
    });

    test("pour confirmer (`null`) : tout ce qui manque, l'étape affichée comprise", () => {
        expect(missingBefore(STEPS, QUESTIONS).map((x) => x.id)).toEqual([1, 2, 3, 5]);
    });

    test("sans étape : ce qui manque pour confirmer, rien pour une étape", () => {
        expect(missingBefore([], [q(1, null, true)]).map((x) => x.id)).toEqual([1]);
        expect(missingBefore([], [q(1, null, true)], 10)).toEqual([]);
    });
});

describe("la page branche les étapes", () => {
    test("les pastilles sont celles du panneau, en haut du VIEWER", () => {
        const viewer = XML.slice(XML.indexOf('class="o_cfg3d_viewer"'), XML.indexOf('class="o_cfg3d_side"'));
        expect(viewer).toContain('class="o_cfg3d_steps"');
        expect(viewer).toContain("o_cfg3d_panel_chip o_cfg3d_step_chip");
        expect(viewer).toContain("this.onStepChip(chip)");
    });

    test("⚠️ grisée mais CLIQUABLE : `aria-disabled`, jamais `disabled`", () => {
        const nav = XML.slice(XML.indexOf('class="o_cfg3d_steps"'), XML.indexOf("</nav>"));
        expect(nav).toContain("t-att-aria-disabled");
        expect(nav).not.toMatch(/\st-att-disabled=/);
    });

    test("la colonne parcourt les questions de l'ÉTAPE", () => {
        expect(XML).toContain('t-foreach="shownQuestions"');
        expect(XML).not.toContain('t-foreach="questions"');
    });

    test("une question se retrouve par son identifiant — pour le défilement et le focus", () => {
        expect(XML).toContain('t-att-data-question-id="question.id"');
        expect(JS).toContain("[data-question-id=");
    });

    test("confirmer passe d'abord par ce qui manque — le même toast et le même défilement", () => {
        const confirm = JS.slice(JS.indexOf("async onConfirm()"));
        expect(confirm.indexOf("_revealMissing")).toBeGreaterThan(-1);
        expect(confirm.indexOf("_revealMissing")).toBeLessThan(confirm.indexOf("/configurator/confirm"));
    });
});

describe("la vue d'une question : la sienne, sinon celle de son étape (D-163, D-387)", () => {
    const VUE_A = { pose: { azimuth: 1 } }, VUE_E = { pose: { azimuth: 2 } };
    const steps = [{ id: 10, name: "Plaques", camera: VUE_E }, { id: 20, name: "Options", camera: null }];

    test("l'attribut qui déclare une vue l'impose", () => {
        expect(questionView({ id: 1, stepId: 10, camera: VUE_A }, steps)).toBe(VUE_A);
    });

    test("sans vue à lui, celle de son étape", () => {
        expect(questionView({ id: 1, stepId: 10, camera: null }, steps)).toBe(VUE_E);
    });

    test("ni l'un ni l'autre : `null` — la caméra ne bouge pas", () => {
        expect(questionView({ id: 1, stepId: 20, camera: null }, steps)).toBe(null);
        expect(questionView({ id: 1, stepId: null, camera: null }, [])).toBe(null);
        expect(questionView(undefined, steps)).toBe(null);
    });

    test("l'état servi porte la vue de chaque question", () => {
        const model = toViewModel({ attributes: [{ id: 1, name: "A", camera: VUE_A, values: [] },
                                                 { id: 2, name: "B", values: [] }] });
        expect(model.questions.map((q) => q.camera)).toEqual([VUE_A, null]);
    });

    test("⚠️ la page ne repose une vue que si elle CHANGE — et l'ouvre au clic comme à la réponse", () => {
        const JS = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");
        const show = JS.slice(JS.indexOf("    _showView(view) {"));
        expect(show.slice(0, show.indexOf("\n    }\n"))).toContain("=== this._shownView) return");
        expect(JS.slice(JS.indexOf("    openPanel("), JS.indexOf("    closePanel("))).toContain("_showQuestionView");
        expect(JS.slice(JS.indexOf("    async onPick("), JS.indexOf("/configurator/set_value\", payload);\n        await this._applyModel(next);\n        this.state.loading = false;\n    }\n\n    /**\n     * Terminer")))
            .toContain("_showQuestionView(questionId)");
    });
});

