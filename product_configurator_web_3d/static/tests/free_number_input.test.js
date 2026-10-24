/**
 * free_number_input.test.js — La saisie libre d'un NOMBRE n'a pas de liste (L-504).
 *
 * La question autorise l'ajout : ses valeurs existantes ne sont qu'une partie des réponses
 * possibles, et la déroulante d'`AutoComplete` se posait sur les onglets du téléphone pendant
 * que le pavé numérique se refermait à la frappe ([[L-504]]). Un champ nu, qui appelle le pavé.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";

const SRC = join(__dirname, "../src/page");
const XML = readFileSync(join(SRC, "configurator_page.xml"), "utf8").replace(/<!--[\s\S]*?-->/g, " ");
const JS = readFileSync(join(SRC, "configurator_page.js"), "utf8");

const free = XML.slice(XML.indexOf('<t t-if="question.free">'), XML.indexOf('class="o_cfg3d_free_unit"'));
const numeric = free.slice(free.indexOf('t-if="question.free.numeric"'), free.indexOf("<AutoComplete"));

describe("saisie libre d'un nombre", () => {
    test("un champ nu, qui appelle le pavé numérique sans manger la virgule (L-218)", () => {
        expect(numeric).toMatch(/^t-if="question\.free\.numeric" type="text" inputmode="decimal"/);
        expect(free).toMatch(/<input t-if="question\.free\.numeric"/);
    });

    test("⚠️ aucune liste de suggestions : ni sources, ni composant à déroulante", () => {
        expect(numeric).not.toContain("sources");
        expect(numeric).not.toContain("AutoComplete");
        expect(JS).not.toContain("NumberAutoComplete");
    });

    test("la réponse part au changement, par la même porte que le texte", () => {
        expect(numeric).toContain('t-on-change="(ev) => this.onFreeChange(placementNodeId, question, ev.target.value)"');
        expect(numeric).toContain('t-att-value="this.freeText(question, placementNodeId)"');
    });

    test("le texte libre garde ses suggestions", () => {
        expect(free).toMatch(/<AutoComplete t-else=""[\s\S]*sources="this\.freeSources\(question\)"/);
    });
});

describe("unité d'une saisie libre", () => {
    const SCSS = readFileSync(join(SRC, "configurator_page.scss"), "utf8");

    test("l'unité est posée dans le cadre du champ, qui lui garde sa place à droite", () => {
        expect(free).toContain(`t-att-class="{'o_cfg3d_free_with_unit': question.free.unit}"`);
        const rule = SCSS.slice(SCSS.indexOf(".o_cfg3d_free_with_unit {"));
        expect(rule).toMatch(/position: relative;[\s\S]*padding-right: 40px;/);
        const unit = SCSS.slice(SCSS.indexOf(".o_cfg3d_free_unit {"));
        expect(unit).toMatch(/position: absolute;[\s\S]*right: 10px;/);
    });

    test("⚠️ un clic sur l'unité traverse jusqu'au champ", () => {
        const unit = SCSS.slice(SCSS.indexOf(".o_cfg3d_free_unit {"), SCSS.indexOf("}", SCSS.indexOf(".o_cfg3d_free_unit {")));
        expect(unit).toContain("pointer-events: none;");
    });
});

describe("la saisie validée reste dans le champ jusqu'à la réponse du serveur (L-617)", () => {
    function setup() {
        const question = { id: 7, free: { numeric: true, unit: "mm" }, customValue: null,
                           values: [{ id: 1, chosen: true, raw: "6", name: "6 mm" }] };
        const page = Object.create(ConfiguratorPage.prototype);
        Object.defineProperty(page, "watching", { value: false });
        page.state = { model: { questions: [question] }, loading: false, reason: null };
        page.render = () => {};
        page._showQuestionViewAfterPaint = async () => {};
        let answer;
        page._call = () => new Promise((resolve) => { answer = resolve; });
        page._applyModel = async () => { question.customValue = "2"; };
        return { page, question, answer: (value) => answer(value) };
    }

    test("pendant l'envoi, le champ montre ce qui a été tapé, pas l'ancienne valeur", async () => {
        const { page, question, answer } = setup();
        page.onFreeChange(null, question, "2");
        expect(page.freeText(question, null)).toBe("2");
        const sending = page._sendFreeAnswer(null, question, "2");
        expect(page.state.loading).toBe(true);
        expect(page.freeText(question, null)).toBe("2");
        answer({});
        await sending;
        expect(page.freeText(question, null)).toBe("2");
        expect(page._freeDrafts.size).toBe(0);
    });

    test("refusée, la saisie s'efface : le champ reprend la réponse rangée, la raison dit pourquoi", async () => {
        const { page, question, answer } = setup();
        page.onFreeChange(null, question, "300");
        const sending = page._sendFreeAnswer(null, question, "300");
        answer({ error: "invalid_custom", message: "200 au plus" });
        await sending;
        expect(page.freeText(question, null)).toBe("6");
        expect(page.state.reason).toBe("200 au plus");
    });

    test("⚠️ retapée pendant l'envoi, la nouvelle saisie n'est pas effacée par la réponse de l'ancienne", async () => {
        const { page, question, answer } = setup();
        page.onFreeChange(null, question, "2");
        const sending = page._sendFreeAnswer(null, question, "2");
        page.onFreeChange(null, question, "3");
        answer({});
        await sending;
        expect(page.freeText(question, null)).toBe("3");
    });

    test("une saisie en attente est propre à la pièce sélectionnée", () => {
        const { page, question } = setup();
        page.onFreeChange(42, question, "9");
        expect(page.freeText(question, 42)).toBe("9");
        expect(page.freeText(question, null)).toBe("6");
    });
});

describe("valider au clavier retire le clavier", () => {
    test("Entrée (la touche → du pavé) quitte le champ ; les autres touches non", () => {
        const page = Object.create(ConfiguratorPage.prototype);
        let blurred = 0;
        const target = { blur: () => { blurred += 1; } };
        page.onFreeKeydown({ key: "5", target });
        expect(blurred).toBe(0);
        page.onFreeKeydown({ key: "Enter", target });
        expect(blurred).toBe(1);
    });

    test("le champ d'un nombre écoute la touche", () => {
        expect(numeric).toContain('t-on-keydown="(ev) => this.onFreeKeydown(ev)"');
    });
});
