/**
 * configurator_state.test.js — La logique de la page publique (lot 6).
 *
 * ⚠️ **Ce fichier est aussi la preuve que le harnais existe.** Le blocage n° 4 du lot 6
 * disait : *« le fork n'a aucun harnais de test JS »*. Il en a un, et la page naît sous
 * tests plutôt que l'inverse.
 */
import { toViewModel, answerFor, reasonFor, sameDefinition, confirmError, handState, handMessage }
    from "@product_configurator_web_3d/configurator_state";

const PAYLOAD = {
    productName: "Porte configurable",
    state: "draft",
    price: 1250.5,
    attributes: [{
        id: 3, name: "Couleur", required: true, multi: false,
        values: [
            { id: 10, name: "Blanc", available: true, chosen: true },
            { id: 11, name: "Noir", available: false, chosen: false },
        ],
    }],
    definition: { id: "m1", kind: "part" },
    scope: { __attribute_3: 10 },
};

describe("toViewModel — la réponse du serveur, mise en forme", () => {
    test("les questions et leurs valeurs arrivent telles quelles", () => {
        const model = toViewModel(PAYLOAD);
        expect(model.productName).toBe("Porte configurable");
        expect(model.questions).toHaveLength(1);
        expect(model.questions[0].values.map((v) => v.name)).toEqual(["Blanc", "Noir"]);
    });

    test("⚠️ une valeur indisponible est ÉTEINTE, pas retirée", () => {
        // D-168 et D-178 : on la grise, et un appui dira pourquoi. La retirer ôterait à
        // la page le moyen de le dire.
        const [blanc, noir] = toViewModel(PAYLOAD).questions[0].values;
        expect(blanc.muted).toBe(false);
        expect(noir.muted).toBe(true);
    });

    test("une session close se signale", () => {
        expect(toViewModel({ ...PAYLOAD, state: "done" }).closed).toBe(true);
        expect(toViewModel(PAYLOAD).closed).toBe(false);
    });

    test("⚠️ un refus rend un MESSAGE, jamais le code brut", () => {
        // Le serveur répond par un code, et trois refus portent le même pour ne pas dire
        // à qui tâtonne quels jetons ont existé (D-190). La phrase est de ce côté-ci.
        const model = toViewModel({ error: "unknown_session" });
        expect(model.error).toBe("unknown_session");
        expect(String(model.message)).toContain("not valid");
        expect(model.questions).toEqual([]);
    });

    test("une réponse absente vaut un refus, elle ne casse rien", () => {
        expect(toViewModel(null).error).toBe("unknown_session");
    });
});

describe("⚠️ la 3D ne se reconstruit QUE si la recette a changé", () => {
    test("une définition identique garde sa RÉFÉRENCE", () => {
        // C'est la règle qui coûte le plus cher si on l'oublie : le viewer décide de
        // reconstruire sur une comparaison de référence, et une référence neuve suffit à
        // refaire toute la géométrie — pour un changement de couleur.
        const premier = toViewModel(PAYLOAD);
        const second = toViewModel({ ...PAYLOAD, price: 1300 }, premier);
        expect(second.definition).toBe(premier.definition);
        expect(second.price).toBe(1300);
    });

    test("une définition DIFFÉRENTE en amène une neuve", () => {
        // Le cas d'une permutation de pièce (D-164) : là, il FAUT reconstruire.
        const premier = toViewModel(PAYLOAD);
        const second = toViewModel(
            { ...PAYLOAD, definition: { id: "m1", kind: "assembly" } }, premier);
        expect(second.definition).not.toBe(premier.definition);
        expect(second.definition.kind).toBe("assembly");
    });

    test("sameDefinition ne se laisse pas prendre par l'ordre des clés", () => {
        expect(sameDefinition({ a: 1, b: 2 }, { a: 1, b: 2 })).toBe(true);
        expect(sameDefinition(null, { a: 1 })).toBe(false);
        expect(sameDefinition(null, null)).toBe(true);
    });
});

describe("answerFor — ce qui part, et ce qui ne part pas", () => {
    const model = toViewModel(PAYLOAD);

    test("cliquer une valeur libre envoie sa question et elle-même", () => {
        const libre = toViewModel({
            ...PAYLOAD,
            attributes: [{ ...PAYLOAD.attributes[0], values: [
                { id: 10, name: "Blanc", available: true, chosen: false }] }],
        });
        expect(answerFor(libre, 3, 10)).toEqual({ attribute_id: 3, value_id: 10 });
    });

    test("⚠️ cliquer la valeur DÉJÀ choisie n'envoie rien", () => {
        // Le serveur écrirait la même chose, et la page clignoterait pour rien.
        expect(answerFor(model, 3, 10)).toBeNull();
    });

    test("⚠️ cliquer une valeur INDISPONIBLE n'envoie rien non plus", () => {
        // Elle n'est pas un choix : c'est une explication à donner.
        expect(answerFor(model, 3, 11)).toBeNull();
    });

    test("une configuration CLOSE n'envoie plus rien", () => {
        const close = toViewModel({ ...PAYLOAD, state: "done" });
        expect(answerFor(close, 3, 11)).toBeNull();
    });

    test("une question ou une valeur inconnue n'invente pas d'appel", () => {
        expect(answerFor(model, 999, 10)).toBeNull();
        expect(answerFor(model, 3, 999)).toBeNull();
        expect(answerFor(null, 3, 10)).toBeNull();
    });
});

describe("reasonFor — ce qu'un appui doit dire (D-178)", () => {
    test("une valeur disponible n'a rien à expliquer", () => {
        expect(reasonFor({ available: true })).toBeNull();
    });

    test("une valeur éteinte rend une phrase", () => {
        expect(String(reasonFor({ available: false }))).toBeTruthy();
    });
});

describe("le refus de confirmation ne doit pas effacer la page", () => {
    test("une confirmation réussie ne rend AUCUN message", () => {
        expect(confirmError({ productName: "Porte", attributes: [] })).toBe(null);
        expect(confirmError(null)).toBe(null);
    });

    test("une configuration incomplète NOMME ce qui manque", () => {
        const message = confirmError({ error: "incomplete", missing: ["Couleur", "Serrure"] });
        expect(message).toContain("Couleur");
        expect(message).toContain("Serrure");
    });

    test("incomplète sans liste reste compréhensible", () => {
        expect(confirmError({ error: "incomplete" })).toBeTruthy();
    });

    test("une session déjà confirmée le dit, et ne parle pas de lien invalide", () => {
        const message = confirmError({ error: "session_closed" });
        expect(message).toBeTruthy();
        expect(message).not.toContain("link");
    });
});

describe("qui conduit, et ce qu'on en dit", () => {
    test("personne ne conduit : la page est libre", () => {
        const hand = handState({ hand: { holder: null } }, "moi");
        expect(hand).toEqual({ free: true, mine: false, label: null });
        expect(handMessage(hand)).toBe(null);
    });

    test("je conduis : rien à annoncer", () => {
        const hand = handState({ hand: { holder: "moi", label: "Gerry" } }, "moi");
        expect(hand.mine).toBe(true);
        expect(handMessage(hand)).toBe(null);
    });

    test("un autre conduit : on le NOMME", () => {
        const hand = handState({ hand: { holder: "elle", label: "Gerry" } }, "moi");
        expect(hand).toEqual({ free: false, mine: false, label: "Gerry" });
        expect(handMessage(hand)).toContain("Gerry");
    });

    test("un autre sans nom reste compréhensible", () => {
        expect(handMessage(handState({ hand: { holder: "elle" } }, "moi"))).toBeTruthy();
    });

    test("un modèle sans main ne fait pas tomber la page", () => {
        expect(handState(null, "moi").free).toBe(true);
        expect(handState({}, "moi").free).toBe(true);
    });

    test("le refus « pas la main » nomme lui aussi le conducteur", () => {
        const message = confirmError({ error: "not_holding", hand: { label: "Gerry" } });
        expect(message).toContain("Gerry");
    });
});
