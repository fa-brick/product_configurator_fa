/**
 * LA LISTE DES RÉPONSES ET LE PANNEAU DE CHOIX, en composants communs — W-113, E-3c-1, D-451.
 *
 * La page du configurateur et la barre de droite de l'éditeur d'environnement les montent à l'identique ; ils ne
 * répondent pas eux-mêmes, ils disent ce qu'on a touché. Éprouvés sans montage (Jest n'a ni bundle ni OWL).
 */
import { AnswerList } from "@product_configurator_web_3d/answers/answer_list";
import { AnswerPanel } from "@product_configurator_web_3d/answers/answer_panel";

const values = (n, chosen = -1) =>
    Array.from({ length: n }, (_, i) => ({ id: i + 1, name: `V${i + 1}`, chosen: i === chosen, categoryKeys: [] }));

function list(props) {
    const self = Object.create(AnswerList.prototype);
    self.props = { onPick: jest.fn(), onOpenPanel: jest.fn(), ...props };
    return self;
}

function panel(props, state = {}) {
    const self = Object.create(AnswerPanel.prototype);
    self.props = { onPick: jest.fn(), onClose: jest.fn(), ...props };
    self.state = { search: "", view: "small", category: null, ...state };
    return self;
}

describe("la liste des réponses", () => {
    test("toucher une réponse la remet à l'hôte, telle quelle", () => {
        const question = { id: 7, displayType: "card", values: values(3) };
        const ed = list({ question });
        ed.pick(question.values[1]);
        expect(ed.props.onPick).toHaveBeenCalledWith(question.values[1]);
    });

    test("la liste déroulante répond par la même porte — une ligne vide ne répond rien", () => {
        const question = { id: 7, displayType: "select", values: values(3) };
        const ed = list({ question });
        ed.onSelect({ target: { value: "2" } });
        expect(ed.props.onPick).toHaveBeenCalledWith(question.values[1]);
        ed.props.onPick.mockClear();
        ed.onSelect({ target: { value: "" } });
        expect(ed.props.onPick).not.toHaveBeenCalled();
    });

    test("« Voir tout » demande le panneau à l'hôte ; sans hôte qui l'écoute, rien ne casse", () => {
        const ed = list({ question: { values: [] } });
        ed.openPanel();
        expect(ed.props.onOpenPanel).toHaveBeenCalled();
        const bare = list({ question: { values: [] }, onOpenPanel: undefined });
        expect(() => bare.openPanel()).not.toThrow();
    });

    test("la rangée `line` partage la largeur que l'hôte a mesurée", () => {
        const question = { displayType: "card", answerSize: "medium", answerLayout: "line", values: values(6) };
        const shown = list({ question, lineWidth: 308 }).shownAnswers(question);
        expect(shown.values.length + shown.more).toBe(6);
        expect(shown.more).toBeGreaterThan(0);
        // ⓘ Sans disposition `line`, tout est montré.
        const inline = { ...question, answerLayout: "inline" };
        expect(list({ question: inline }).shownAnswers(inline)).toEqual({ values: inline.values, more: 0 });
    });

    test("en mode compact, une grille devient une rangée qui défile (D-389)", () => {
        const question = { displayType: "card", answerLayout: "inline", values: values(2) };
        expect(list({ question, compact: true }).layoutOn(question)).toBe("scroll");
        expect(list({ question }).layoutOn(question)).toBe("inline");
    });
});

describe("le panneau de choix", () => {
    const question = {
        displayType: "swatch",
        categories: [{ key: "m1", name: "Chêne" }, { key: "m2", name: "Pin" }],
        values: [
            { id: 1, name: "Chêne brut", categoryKeys: ["m1"] },
            { id: 2, name: "Chêne huilé", categoryKeys: ["m1"] },
            { id: 3, name: "Pin", categoryKeys: ["m2"] },
        ],
    };

    test("la recherche, la vue et la catégorie sont les siennes — la page ne les garde plus", () => {
        const ed = panel({ question });
        ed.onPanelCategory("m1");
        expect(ed.panelValues(question).map((v) => v.id)).toEqual([1, 2]);
        ed.onPanelSearch({ target: { value: "huil" } });
        expect(ed.panelValues(question).map((v) => v.id)).toEqual([2]);
        ed.onPanelView("large");
        expect(ed.state.view).toBe("large");
    });

    test("une réponse et la fermeture passent par l'hôte", () => {
        const ed = panel({ question });
        ed.pick(question.values[2]);
        expect(ed.props.onPick).toHaveBeenCalledWith(question.values[2]);
        expect(ed.props.onPick).toHaveBeenCalledTimes(1);
    });

    test("les pastilles de catégories : « Tout » d'abord, puis une par catégorie", () => {
        const chips = panel({ question }).panelChips(question);
        expect(chips[0].key).toBe(null);
        expect(chips.map((c) => c.key).slice(1)).toEqual(["m1", "m2"]);
    });
});
