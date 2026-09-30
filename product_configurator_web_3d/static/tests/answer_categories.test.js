/**
 * LES PASTILLES DE CATÉGORIES du panneau de choix — D-382, lot 4b (Gerry : « des pastilles
 * horizontales sous la recherche qui filtrent », « autre et tout »).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { toViewModel, panelChips, filterByCategory, OTHER_CATEGORY }
    from "@product_configurator_web_3d/configurator_state";

const SRC = join(__dirname, "..", "src");
const XML = readFileSync(join(SRC, "page", "configurator_page.xml"), "utf8")
    .replace(/<!--[\s\S]*?-->/g, " ");
const JS = readFileSync(join(SRC, "page", "configurator_page.js"), "utf8");

const question = (values, categories) => ({ values, categories });
const v = (id, keys) => ({ id, name: `V${id}`, categoryKeys: keys });

describe("les pastilles d'une question", () => {
    test("« Tout », les catégories dans l'ordre servi, « Autres » s'il reste des réponses sans", () => {
        const q = question([v(1, ["m1"]), v(2, ["m2"]), v(3, [])],
                           [{ key: "m2", name: "Noyer" }, { key: "m1", name: "Chêne" }]);
        expect(panelChips(q, "Tout", "Autres")).toEqual([
            { key: null, label: "Tout" },
            { key: "m2", label: "Noyer" },
            { key: "m1", label: "Chêne" },
            { key: OTHER_CATEGORY, label: "Autres" },
        ]);
    });

    test("⚠️ aucune pastille sous DEUX groupes — une seule catégorie ne filtrerait rien", () => {
        expect(panelChips(question([v(1, ["m1"]), v(2, ["m1"])], [{ key: "m1", name: "Chêne" }]), "T", "A"))
            .toEqual([]);
        expect(panelChips(question([v(1, []), v(2, [])], []), "T", "A")).toEqual([]);
        // Une catégorie ET des réponses sans : deux groupes, donc des pastilles.
        expect(panelChips(question([v(1, ["m1"]), v(2, [])], [{ key: "m1", name: "Chêne" }]), "T", "A"))
            .toHaveLength(3);
    });
});

describe("le filtre d'une pastille", () => {
    const values = [v(1, ["m1"]), v(2, ["w7", "m2"]), v(3, [])];

    test("« Tout » : tout", () => {
        expect(filterByCategory(values, null)).toBe(values);
    });

    test("une catégorie : ses réponses seulement — un produit sous PLUSIEURS s'y trouve", () => {
        expect(filterByCategory(values, "m2").map((x) => x.id)).toEqual([2]);
        expect(filterByCategory(values, "w7").map((x) => x.id)).toEqual([2]);
    });

    test("« Autres » : les réponses sans catégorie", () => {
        expect(filterByCategory(values, OTHER_CATEGORY).map((x) => x.id)).toEqual([3]);
    });
});

describe("ce que la page reçoit, et ce qu'elle en garde", () => {
    test("⚠️ les clés et les catégories passent la mise en forme ([[L-212]])", () => {
        const payload = { attributes: [{
            id: 1, name: "Essence", displayType: "swatch",
            categories: [{ key: "m1", name: "Chêne" }],
            values: [{ id: 10, name: "Chêne brut", categoryKeys: ["m1"] }, { id: 11, name: "Sans" }],
        }] };
        const q = toViewModel(payload).questions[0];
        expect(q.categories).toEqual([{ key: "m1", name: "Chêne" }]);
        expect(q.values[0].categoryKeys).toEqual(["m1"]);
        expect(q.values[1].categoryKeys).toEqual([]);
    });

    test("le panneau filtre par la pastille PUIS par la recherche, et s'ouvre sur « Tout »", () => {
        const body = JS.slice(JS.indexOf("    panelValues(question) {"), JS.indexOf("    panelChips(question) {"));
        expect(body).toContain("filterAnswers(filterByCategory(question.values, panel.category), panel.search)");
        expect(JS).toMatch(/view: panelViewOf\(question\),\s*category: null,/);
    });

    test("les pastilles sont sous la recherche, et disent laquelle est active", () => {
        const panel = XML.slice(XML.indexOf('t-name="product_configurator_web_3d.AnswerPanel"'));
        const tools = panel.indexOf('class="o_cfg3d_panel_tools"');
        const chips = panel.indexOf('class="o_cfg3d_panel_chips"');
        const body = panel.indexOf('class="o_cfg3d_panel_body"');
        expect(tools).toBeGreaterThan(0);
        expect(chips).toBeGreaterThan(tools);
        expect(body).toBeGreaterThan(chips);
        expect(panel).toContain("'o_cfg3d_panel_chip--on': state.panel.category === chip.key");
        expect(panel).toContain('t-on-click="() => this.onPanelCategory(chip.key)"');
    });
});
