/**
 * configurator_state.test.js — La logique de la page publique (lot 6).
 *
 * ⚠️ **Ce fichier est aussi la preuve que le harnais existe.** Le blocage n° 4 du lot 6
 * disait : *« le fork n'a aucun harnais de test JS »*. Il en a un, et la page naît sous
 * tests plutôt que l'inverse.
 */
import { toViewModel, answerFor, reasonFor, sameDefinition, confirmError, handState, handMessage,
         placementOf, selectableNodeIds, answerForPlacement }
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

describe("la SORTIE de la page — l'URL du produit", () => {
    test("elle traverse la mise en forme telle quelle", () => {
        const model = toViewModel({ ...PAYLOAD, productUrl: "/shop/porte-42" });
        expect(model.productUrl).toBe("/shop/porte-42");
    });

    test("⚠️ `null` quand le serveur n'en donne pas — et NON `undefined`", () => {
        // Le gabarit teste `canClose` : une absence doit valoir « pas de sortie », pas
        // « clé manquante ». Une base sans site (`website` absent) est ce cas-là, et la
        // croix ne doit alors pas se dessiner plutôt que mener nulle part.
        expect(toViewModel(PAYLOAD).productUrl).toBeNull();
    });
});

describe("⚠️ la CUISSON et l'AMBIANCE traversent la mise en forme", () => {
    // Le serveur les émettait, la page les lisait, et `toViewModel` — une liste blanche —
    // les laissait tomber : le chemin des GLB cuits n'avait JAMAIS tourné sur la page
    // publique, et l'ambiance n'atteignait pas le viewer ([[L-212]]). Relevé le 2026-09-22.
    test("les pièces cuites arrivent telles quelles", () => {
        const baked = { c12: { attachmentId: 77, faces: { f3d_7: [] } } };
        expect(toViewModel({ ...PAYLOAD, baked }).baked).toEqual(baked);
    });

    test("l'ambiance aussi", () => {
        const ambience = { toneMapping: "aces", exposure: 1.2 };
        expect(toViewModel({ ...PAYLOAD, ambience }).ambience).toEqual(ambience);
    });

    test("absentes, elles valent `null` — la page sait quoi en faire", () => {
        const model = toViewModel(PAYLOAD);
        expect(model.baked).toBeNull();
        expect(model.ambience).toBeNull();
    });

    test("⚠️ TOUT ce que la page lit sur le modèle est produit ici", () => {
        // La garde de classe : une clé lue par la page et absente de cette liste blanche
        // vaut `undefined` sans une erreur — c'est exactement comment la cuisson et
        // l'ambiance se sont perdues. Les commentaires sont retirés avant de chercher
        // ([[L-352]]).
        const { readFileSync } = require("node:fs");
        const { join } = require("node:path");
        const strip = (src) => src.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ");
        const page = strip(readFileSync(join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8"));
        const template = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.xml"), "utf8")
            .replace(/<!--[\s\S]*?-->/g, " ");
        const state = strip(readFileSync(join(__dirname, "..", "src", "configurator_state.js"), "utf8"));
        const read = new Set();
        for (const src of [page, template]) {
            for (const m of src.matchAll(/\bmodel(?:\?\.|\.)(\w+)/g)) read.add(m[1]);
        }
        const body = state.slice(state.indexOf("export function toViewModel"),
                                 state.indexOf("export function sameDefinition"));
        // ⓘ `clé: valeur` comme `clé,` (raccourci), et la branche d'erreur, indentée d'un cran.
        const produced = new Set([...body.matchAll(/^\s{8,12}(\w+)(?::|,\s*$)/gm)].map((m) => m[1]));
        expect(read.size).toBeGreaterThan(8);
        expect([...read].filter((k) => !produced.has(k))).toEqual([]);
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

describe("la forme d'une question, et la réponse multiple", () => {
    const question = (extra = {}) => toViewModel({
        productName: "Porte", price: 0,
        attributes: [{
            id: 3, name: "Couleur", displayType: "card", multi: false,
            values: [
                { id: 7, name: "Blanc", available: true, chosen: true, color: "#fff",
                  image: "/configurator/value/7/image" },
                { id: 8, name: "Noir", available: true, chosen: false },
            ],
            ...extra,
        }],
    });

    test("la forme voyage jusqu'à la page", () => {
        expect(question().questions[0].displayType).toBe("card");
    });

    test("une question SANS forme déclarée retombe sur `radio`, elle ne disparaît pas", () => {
        const modele = toViewModel({ attributes: [{ id: 1, name: "X", values: [] }] });
        expect(modele.questions[0].displayType).toBe("radio");
    });

    test("la pastille et la vignette suivent la valeur", () => {
        const [blanc, noir] = question().questions[0].values;
        expect(blanc.color).toBe("#fff");
        expect(blanc.image).toBe("/configurator/value/7/image");
        // ⓘ `null` veut dire « il n'y en a pas », jamais « on ne sait pas ».
        expect(noir.color).toBe(null);
        expect(noir.image).toBe(null);
    });

    test("re-cliquer une réponse UNIQUE déjà retenue ne renvoie rien", () => {
        expect(answerFor(question(), 3, 7)).toBe(null);
    });

    test("⚠️ re-cliquer une réponse MULTIPLE la décoche — sinon le choix serait sans retour", () => {
        const modele = question({ multi: true, displayType: "multi" });
        expect(answerFor(modele, 3, 7)).toEqual({ attribute_id: 3, value_id: 7 });
    });

    test("une valeur indisponible ne part jamais, multiple ou non", () => {
        const modele = toViewModel({
            attributes: [{ id: 3, name: "Couleur", multi: true, values: [
                { id: 9, name: "Rouge", available: false, chosen: false },
            ] }],
        });
        expect(answerFor(modele, 3, 9)).toBe(null);
    });
});

describe("les PLACEMENTS réglables — ce qui se sélectionne, et ce qu'on y répond (D-332, D-333)", () => {
    const PLACEMENTS = {
        c11: { linkId: 11, label: "Poignée", questions: [{
            id: 5, name: "Couleur de poignée", multi: false, displayType: "color",
            values: [{ id: 50, name: "Blanc", available: true, chosen: true },
                     { id: 51, name: "Noir", available: true, chosen: false },
                     { id: 52, name: "Rouge", available: false, chosen: false }],
        }] },
    };
    const model = () => toViewModel({ ...PAYLOAD, placements: PLACEMENTS });
    /** La projection du moteur : un sous-ensemble, sa poignée, une copie, un rail piloté. */
    const PIECES = [
        { key: "c10", pieceId: 1, nodeId: "c10", label: "Sous-ensemble", linkId: 10, sourceLinkId: 10, parentKey: "m1" },
        { key: "c11", pieceId: 2, nodeId: "c11", label: "Poignée", linkId: 11, sourceLinkId: 11, parentKey: "c10" },
        { key: "c11/f5/occ_001", pieceId: 2, nodeId: "c11/f5/occ_001", label: "Poignée", linkId: null,
          sourceLinkId: 11, occurrence: { of: "c11" }, parentKey: "c10" },
        { key: "c12", pieceId: 3, nodeId: "c12", label: "Rail", linkId: 12, sourceLinkId: 12, parentKey: "c10" },
    ];

    test("les placements traversent la mise en forme, avec la forme d'une question", () => {
        const placement = model().placements.c11;
        expect(placement.linkId).toBe(11);
        expect(placement.label).toBe("Poignée");
        expect(placement.questions[0].displayType).toBe("color");
        expect(placement.questions[0].values[2].muted).toBe(true);
    });

    test("absents, `{}` — jamais `undefined`", () => {
        expect(toViewModel(PAYLOAD).placements).toEqual({});
    });

    test("⚠️ seules les pièces à questions éditables sont sélectionnables — le rail ne l'est pas", () => {
        expect([...selectableNodeIds(model(), PIECES)].sort()).toEqual(["c11", "c11/f5/occ_001"]);
    });

    test("⚠️ une COPIE se règle par le lien de sa source", () => {
        expect(placementOf(model(), PIECES, "c11/f5/occ_001")?.linkId).toBe(11);
        expect(placementOf(model(), PIECES, "c12")).toBeNull();
        expect(placementOf(model(), PIECES, "nulle-part")).toBeNull();
    });

    test("⚠️ un placement IMBRIQUÉ se trouve par son CHEMIN, jamais par `c<lien>` (D-349)", () => {
        // Deux poses d'un même sous-ensemble : la poignée a le MÊME lien sous les deux,
        // et le serveur range chaque placement sous l'identité de sa pose.
        const nested = toViewModel({ ...PAYLOAD, placements: {
            "c10/c11": { ...PLACEMENTS.c11, label: "Poignée gauche" },
            "c20/c11": { ...PLACEMENTS.c11, label: "Poignée droite" },
        } });
        const pieces = [
            { key: "c10/c11", nodeId: "c10/c11", linkId: 11, parentKey: "c10" },
            { key: "c20/c11", nodeId: "c20/c11", linkId: 11, parentKey: "c20" },
        ];
        expect(placementOf(nested, pieces, "c10/c11")?.label).toBe("Poignée gauche");
        expect(placementOf(nested, pieces, "c20/c11")?.label).toBe("Poignée droite");
    });

    test("répondre sur un placement envoie le LIEN avec la valeur", () => {
        const m = model();
        expect(answerForPlacement(m, m.placements.c11, 5, 51))
            .toEqual({ attribute_id: 5, value_id: 51, link_id: 11 });
    });

    test("⚠️ mêmes refus que pour la racine : déjà choisie, indisponible, session close", () => {
        const m = model();
        expect(answerForPlacement(m, m.placements.c11, 5, 50)).toBeNull();   // déjà choisie
        expect(answerForPlacement(m, m.placements.c11, 5, 52)).toBeNull();   // indisponible
        expect(answerForPlacement({ ...m, closed: true }, m.placements.c11, 5, 51)).toBeNull();
        expect(answerForPlacement(m, null, 5, 51)).toBeNull();
    });
});
