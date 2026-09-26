/**
 * free_answer.test.js — La SAISIE LIBRE sur la page du configurateur (D-353).
 *
 * Une question dont la ligne autorise l'ajout se répond dans un champ, que sa liste de
 * valeurs vient SUGGÉRER. Ce fichier éprouve ce que la page en fait : la forme du champ,
 * ce qu'il affiche, ce qu'il envoie — et surtout ce qu'il N'ENVOIE PAS.
 */
import { toViewModel, freeText, boundsLabel, freeSuggestions, customAnswerFor, customError }
    from "@product_configurator_web_3d/configurator_state";

const WIDTH = {
    id: 2469, name: "Largeur intérieure", required: true, multi: false,
    displayType: "select",
    free: { numeric: true, unit: "mm", min: 100, max: 600, step: null,
            maxLength: null, regexp: null },
    customValue: null,
    values: [
        { id: 4155, name: "150 mm", raw: "150", available: true, chosen: true },
        { id: 4175, name: "200 mm", raw: "200", available: true, chosen: false },
        { id: 4176, name: "300 mm", raw: "300", available: false, chosen: false },
    ],
};

const ENGRAVING = {
    id: 90, name: "Gravure", required: false, multi: false, displayType: "radio",
    free: { numeric: false, unit: "", min: null, max: null, step: null,
            maxLength: 20, regexp: null },
    customValue: "Paul",
    values: [{ id: 91, name: "Sans", raw: "Sans", available: true, chosen: false }],
};

function model(...attributes) {
    return toViewModel({ productName: "Caisse", state: "draft", attributes });
}

describe("la forme du champ arrive jusqu'à la page", () => {
    test("une question avec ajout porte son champ ; les autres n'en ont pas", () => {
        const closed = { ...WIDTH, id: 1, free: null };
        const [width, other] = model(WIDTH, closed).questions;
        expect(width.free).toEqual({ numeric: true, unit: "mm", min: 100, max: 600,
                                     step: null, maxLength: null, regexp: null });
        expect(other.free).toBeNull();
    });

    test("⚠️ une borne à ZÉRO reste une borne", () => {
        // `|| null` l'aurait effacée : « ≥ 0 » serait devenu « pas de borne ».
        const [q] = model({ ...WIDTH, free: { ...WIDTH.free, min: 0, max: null } }).questions;
        expect(q.free.min).toBe(0);
        expect(boundsLabel(q)).toBe("≥ 0 mm");
    });

    test("la saisie en cours et la forme rangée des valeurs traversent", () => {
        // ⚠️ `toViewModel` est une LISTE BLANCHE ([[L-212]]) : un champ servi qu'elle
        // oublie n'atteint jamais la page.
        const [engraving] = model(ENGRAVING).questions;
        expect(engraving.customValue).toBe("Paul");
        const [width] = model(WIDTH).questions;
        expect(width.values[0].raw).toBe("150");
    });
});

describe("ce que le champ affiche", () => {
    test("la saisie, sinon la FORME RANGÉE de la valeur choisie — sans son unité", () => {
        const [width] = model(WIDTH).questions;
        expect(freeText(width)).toBe("150");
        const [engraving] = model(ENGRAVING).questions;
        expect(freeText(engraving)).toBe("Paul");
    });

    test("le nombre revient avec la VIRGULE du visiteur", () => {
        const [q] = model({ ...WIDTH, customValue: "2.5" }).questions;
        expect(freeText(q, ",")).toBe("2,5");
        expect(freeText(q, ".")).toBe("2.5");
    });

    test("un texte n'est jamais « localisé »", () => {
        const [q] = model({ ...ENGRAVING, customValue: "v1.2" }).questions;
        expect(freeText(q, ",")).toBe("v1.2");
    });
});

describe("la contrainte, sous le champ", () => {
    test("un nombre borné : « mini → maxi unité »", () => {
        const [q] = model(WIDTH).questions;
        expect(boundsLabel(q)).toBe("100 → 600 mm");
    });

    test("un texte : sa longueur maxi", () => {
        const [q] = model(ENGRAVING).questions;
        expect(boundsLabel(q)).toBe("20 characters max");
    });

    test("rien quand rien n'est borné — et rien pour une question sans champ", () => {
        const [q] = model({ ...WIDTH, free: { ...WIDTH.free, min: null, max: null } }).questions;
        expect(boundsLabel(q)).toBe("");
        expect(boundsLabel({ free: null })).toBe("");
    });
});

describe("les suggestions", () => {
    test("les valeurs offertes, filtrées sur la frappe — la valeur part par son identifiant", () => {
        const [q] = model(WIDTH).questions;
        expect(freeSuggestions(q, "20")).toEqual([{ label: "200 mm", value: 4175 }]);
    });

    test("⚠️ une valeur ÉTEINTE n'est pas suggérée — le serveur la refuserait", () => {
        const [q] = model(WIDTH).questions;
        expect(freeSuggestions(q).map((o) => o.value)).toEqual([4155, 4175]);
    });
});

describe("ce qui part au serveur", () => {
    test("une saisie neuve part, avec son texte brut", () => {
        const m = model(WIDTH);
        expect(customAnswerFor(m, m.questions[0], " 480 "))
            .toEqual({ attribute_id: 2469, custom_value: "480" });
    });

    test("⚠️ quitter un champ qu'on n'a PAS modifié n'envoie rien", () => {
        // Sinon : reconstruction de la 3D et diffusion à tous ceux qui regardent, pour
        // rien (D-253).
        const m = model(WIDTH);
        expect(customAnswerFor(m, m.questions[0], "150")).toBeNull();
        const m2 = model({ ...WIDTH, customValue: "2.5" });
        expect(customAnswerFor(m2, m2.questions[0], "2,5", null, ",")).toBeNull();
    });

    test("une saisie VIDE part : c'est le geste qui efface la réponse tapée", () => {
        const m = model(ENGRAVING);
        expect(customAnswerFor(m, m.questions[0], "")).toEqual({ attribute_id: 90, custom_value: "" });
    });

    test("pour un placement, le lien part avec la saisie", () => {
        const m = model(WIDTH);
        expect(customAnswerFor(m, m.questions[0], "480", { linkId: 6342 }))
            .toEqual({ attribute_id: 2469, custom_value: "480", link_id: 6342 });
    });

    test("rien ne part d'une configuration close, ni d'une question sans champ", () => {
        const closed = toViewModel({ state: "done", attributes: [WIDTH] });
        expect(customAnswerFor(closed, closed.questions[0], "480")).toBeNull();
        const m = model({ ...WIDTH, free: null });
        expect(customAnswerFor(m, m.questions[0], "480")).toBeNull();
    });
});

describe("ce que la page dit d'un refus", () => {
    test("le message du SERVEUR, tel quel — c'est lui qui connaît la borne", () => {
        const msg = "Custom value 900 for 'Largeur intérieure' is above the maximum of 600.";
        expect(customError({ error: "invalid_custom", message: msg })).toBe(msg);
    });

    test("une question qui n'accepte pas de saisie", () => {
        expect(customError({ error: "custom_not_allowed" }))
            .toBe("This question does not accept a typed answer.");
    });

    test("un état n'est pas un refus", () => {
        expect(customError({ productName: "Caisse" })).toBeNull();
    });
});
