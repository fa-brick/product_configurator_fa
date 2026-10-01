/**
 * LE PANNEAU DE CHOIX, LA LIGNE « +N », LA LIGNE RÉSUMÉ — D-382, lot 3.
 * Logique pure éprouvée directement ; gabarit, composant et feuille de style lus dans les
 * sources, commentaires retirés ([[L-352]]) — Jest n'a ni bundle ni OWL.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { lineOf, filterAnswers, searchable, panelViewOf, pickedAnswer, isImageForm, ANSWER_MIN_WIDTH }
    from "@product_configurator_web_3d/configurator_state";

const SRC = join(__dirname, "..", "src");
const XML = readFileSync(join(SRC, "page", "configurator_page.xml"), "utf8")
    .replace(/<!--[\s\S]*?-->/g, " ");
const SCSS = readFileSync(join(SRC, "page", "configurator_page.scss"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ");
const JS = readFileSync(join(SRC, "page", "configurator_page.js"), "utf8");

const values = (n, chosen = -1) =>
    Array.from({ length: n }, (_, i) => ({ id: i + 1, name: `V${i + 1}`, chosen: i === chosen }));
/**
 * Le corps d'une méthode du composant, jusqu'à la suivante.
 * ⚠️ Lève si elle est introuvable : une tranche VIDE ferait passer tout « ne contient pas »
 * (`async onAnswer` échappait d'abord au motif, et le test passait sur rien).
 */
const method = (name) => {
    const start = JS.search(new RegExp(`^ {4}(get |async )?${name}\\(`, "m"));
    if (start < 0) throw new Error(`méthode introuvable : ${name}`);
    const end = JS.slice(start + 1).search(/^ {4}(get |async )?[_a-zA-Z]+\(.*\) \{$/m);
    const body = JS.slice(start, end < 0 ? undefined : start + 1 + end);
    if (body.length < 20) throw new Error(`méthode vide : ${name}`);
    return body;
};

describe("la ligne « +N » — ce qu'une seule ligne montre", () => {
    // Colonne de 308 px : cartes moyennes (96 px) → 3 par ligne, petites (64) → 4.
    test("tout tient : tout est montré, pas de « +N »", () => {
        expect(lineOf(values(3), 308, "card", "medium")).toEqual({ values: values(3), more: 0 });
    });

    test("trop de réponses : la dernière case devient « +N »", () => {
        const line = lineOf(values(10), 308, "card", "medium");
        expect(line.values.map((v) => v.id)).toEqual([1, 2]);
        expect(line.more).toBe(8);
        const small = lineOf(values(10), 308, "card", "small");
        expect(small.values).toHaveLength(3);
        expect(small.more).toBe(7);
    });

    test("⚠️ le choix est TOUJOURS dans la ligne — il prend la dernière place visible", () => {
        const line = lineOf(values(10, 7), 308, "card", "medium");
        expect(line.values.map((v) => v.id)).toEqual([1, 8]);
        expect(line.more).toBe(8);
    });

    test("la grande pastille compte la marge intérieure de sa grille", () => {
        // 308 − 8 = 300 utiles, cases de 84 px : 3 → 2 réponses + « +N ».
        expect(lineOf(values(15), 308, "swatch", "medium").values).toHaveLength(2);
        expect(ANSWER_MIN_WIDTH.swatch.medium).toBe(84);
    });

    test("sans largeur mesurée : tout, plutôt qu'une ligne tronquée au hasard", () => {
        expect(lineOf(values(15), 0, "card", "medium").more).toBe(0);
    });

    test("les largeurs minimales sont CELLES de la feuille de style", () => {
        for (const [form, grid] of [["card", "o_cfg3d_cards"], ["swatch", "o_cfg3d_bigswatches"]]) {
            const body = SCSS.slice(SCSS.indexOf(`.${grid} {`));
            const base = Number(body.match(/minmax\((\d+)px, 1fr\)/)[1]);
            const small = Number(body.match(/&--small \{ grid-template-columns: repeat\(auto-fill, minmax\((\d+)px/)[1]);
            const large = Number(body.match(/&--large \{ grid-template-columns: repeat\(auto-fill, minmax\((\d+)px/)[1]);
            expect(ANSWER_MIN_WIDTH[form]).toEqual({ small, medium: base, large });
        }
    });
});

describe("la recherche du panneau", () => {
    const list = [{ name: "Crème" }, { name: "Gris clair" }, { name: "Blanc cassé" }];

    test("sans accents ni casse — « creme » trouve « Crème »", () => {
        expect(filterAnswers(list, "creme").map((v) => v.name)).toEqual(["Crème"]);
        expect(filterAnswers(list, "  CASSÉ ").map((v) => v.name)).toEqual(["Blanc cassé"]);
        expect(searchable("Écru")).toBe("ecru");
    });

    test("vide : toutes les réponses", () => {
        expect(filterAnswers(list, "")).toBe(list);
    });
});

describe("la vue d'ouverture et le choix résumé", () => {
    test("une forme à image s'ouvre en grille ; les autres n'ont que la liste", () => {
        expect(panelViewOf({ displayType: "card", answerSize: "large" })).toBe("large");
        expect(panelViewOf({ displayType: "card", answerSize: "medium" })).toBe("small");
        expect(panelViewOf({ displayType: "swatch", answerSize: "small" })).toBe("small");
        for (const form of ["radio", "pills", "select"]) {
            expect(panelViewOf({ displayType: form, answerSize: "large" })).toBe("list");
        }
        expect(isImageForm({ displayType: "radio" })).toBe(false);
    });

    test("le choix d'une question, ou rien", () => {
        expect(pickedAnswer({ values: values(3, 1) }).id).toBe(2);
        expect(pickedAnswer({ values: values(3) })).toBeNull();
    });
});

describe("le panneau — ce que la page en garde, et quand il se ferme", () => {
    test("⚠️ l'état ne garde que des IDENTIFIANTS, jamais la question ([[L-449]])", () => {
        const open = method("openPanel");
        expect(open).toMatch(/this\.state\.panel = \{\s*nodeId: nodeId \|\| null, questionId: question\.id, search: "", view: panelViewOf\(question\),\s*category: null,\s*\};/);
    });

    test("⚠️ la question est RELUE par un getter qui n'écrit rien ([[L-384]])", () => {
        const getter = method("panelQuestion");
        expect(getter).toContain("get panelQuestion()");
        expect(getter).not.toMatch(/this\.[a-zA-Z_.]+ = /);
    });

    test("il reste ouvert après une réponse — seul « Retour » le ferme (Gerry)", () => {
        for (const name of ["onAnswer", "onPick"]) {
            expect(method(name)).not.toContain("panel");
        }
        expect(XML).toContain('t-on-click="() => this.closePanel()"');
    });

    test("Échap ferme le panneau AVANT la sélection ; changer de pièce le ferme", () => {
        expect(JS).toMatch(/if \(this\.state\.panel\) this\.closePanel\(\);\s*else if \(this\.state\.selection\.nodeId\) this\.onClearSelection\(\);/);
        expect(method("_select")).toContain("this.state.panel = null;");
    });

    test("pas de clavier imposé au doigt : la recherche ne prend le focus qu'à la souris", () => {
        expect(method("_afterRender")).toMatch(/if \(window\.matchMedia\("\(hover: hover\)"\)\.matches\) \{\s*this\.panelSearchRef\.el\.focus\(\{ preventScroll: true \}\);/);
    });

    test("une seule définition de chaque méthode neuve ([[L-361]])", () => {
        for (const name of ["openPanel", "closePanel", "panelValues", "onPanelSearch", "onPanelView",
                            "shownAnswers", "pickedAnswer", "isImageForm", "_afterRender", "_observeAnswers"]) {
            expect(JS.match(new RegExp(`^ {4}${name}\\(`, "gm"))).toHaveLength(1);
        }
    });
});

describe("le gabarit du panneau, de la ligne et du résumé", () => {
    const panel = XML.slice(XML.indexOf('t-name="product_configurator_web_3d.AnswerPanel"'),
                            XML.indexOf('t-name="product_configurator_web_3d.ScrollArrows"'));
    const question = XML.slice(XML.indexOf('t-name="product_configurator_web_3d.Question"'),
                               XML.indexOf('t-name="product_configurator_web_3d.Card"'));

    test("la carte et la pastille sont UN bouton, appelé par la question ET le panneau", () => {
        for (const name of ["Card", "BigSwatch"]) {
            const call = `<t t-call="product_configurator_web_3d.${name}"/>`;
            expect(question).toContain(call);
            expect(panel).toContain(call);
        }
    });

    test("⚠️ la raison d'un refus s'affiche DANS le panneau (D-178)", () => {
        expect(panel).toContain('<p t-if="state.reason" class="o_cfg3d_reason o_cfg3d_panel_reason" t-esc="state.reason"/>');
    });

    test("le panneau répond par la même porte, pour la bonne pièce", () => {
        expect(panel).toContain('<t t-set="placementNodeId" t-value="state.panel.nodeId"/>');
        expect(panel).toContain("this.onAnswer(placementNodeId, question.id, value)");
    });

    test("la bascule de vue n'existe que pour les formes à image", () => {
        expect(panel).toMatch(/<div t-if="this\.isImageForm\(question\)" class="o_cfg3d_panel_views"/);
    });

    test("le résumé passe après la saisie libre, avant les formes ; le titre ne s'y répète pas", () => {
        const free = question.indexOf('<t t-if="question.free">');
        const summary = question.indexOf(`t-elif="question.answerLayout === 'summary'"`);
        const card = question.indexOf(`t-elif="question.displayType === 'card'"`);
        expect(free).toBeGreaterThan(0);
        expect(summary).toBeGreaterThan(free);
        expect(card).toBeGreaterThan(summary);
        // ⓘ Et jamais en mode compact : l'onglet porte le nom (D-389).
        expect(question).toMatch(/<h2 t-if="!state.compact and \(question.free or question.answerLayout !== 'summary'\)"\s*t-esc="question.name"\/>/);
    });

    test("« +N » : dans les deux grilles, il ouvre le panneau", () => {
        const more = question.match(/<button t-if="shown\.more"[^>]*\s+t-on-click="\(\) => this\.openPanel\(placementNodeId, question\)">/g);
        expect(more).toHaveLength(2);
        expect(question.match(/<t t-set="shown" t-value="this\.shownAnswers\(question\)"\/>/g)).toHaveLength(2);
    });
});

describe("la feuille de style du panneau", () => {
    const panel = SCSS.slice(SCSS.indexOf(".o_cfg3d_panel {"), SCSS.indexOf("@keyframes o_cfg3d_panel_from_right"));

    test("par-dessus la colonne, qui le borne ET le rogne — sur téléphone aussi, depuis D-389", () => {
        const side = SCSS.slice(SCSS.indexOf(".o_cfg3d_side {"), SCSS.indexOf(".o_cfg3d_scroll {"));
        expect(side).toContain("position: relative;");
        // Sans rognage, le panneau qui glisse dépassait, et le focus faisait défiler la page.
        expect(side).toContain("overflow: hidden;");
        expect(panel).toMatch(/position: absolute;\s*inset: 0;/);
        // ⓘ D-389 : plus de plein écran sur téléphone — c'est la colonne qui grandit
        // (`compact_panel.test.js`), et la 3D reste visible au-dessus.
        expect(panel).not.toMatch(/position: fixed;/);
    });

    test("il glisse depuis la droite, ou monte depuis le bas — et reste immobile si on le demande", () => {
        expect(panel).toContain("animation: o_cfg3d_panel_from_right");
        expect(panel).toContain("animation-name: o_cfg3d_panel_from_bottom;");
        expect(panel).toMatch(/@media \(prefers-reduced-motion: reduce\) \{ animation: none; \}/);
    });
});
