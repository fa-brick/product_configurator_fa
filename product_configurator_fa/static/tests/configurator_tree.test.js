/**
 * configurator_tree.test.js — la mise à plat de l'arbre (D-210).
 *
 * ⚠️ Une valeur ne s'affiche QUE si son attribut est déplié. Tout rendre et
 * cacher en CSS ferait payer un produit à trois cents valeurs pour rien — c'est
 * précisément le cas que le dialogue existe pour éviter (D-206).
 */
import {flattenTree} from "../src/js/configurator_tree.esm.js";

const ARBRE = [
    {kind: "attribute", id: 1, name: "Type de Camplate", values: [
        {kind: "value", id: 11, name: "Classic"},
        {kind: "value", id: 12, name: "Ciné"},
    ]},
    {kind: "step", id: 9, name: "Formes du drone"},
    {kind: "attribute", id: 2, name: "Forme", values: []},
];

describe("L'arbre se met à plat dans l'ordre où il s'affiche", () => {
    test("replié, un attribut ne montre AUCUNE de ses valeurs", () => {
        const plat = flattenTree(ARBRE, new Set());
        expect(plat.map((r) => r.name)).toEqual([
            "Type de Camplate", "Formes du drone", "Forme",
        ]);
    });

    test("déplié, ses valeurs le suivent — et elles seules", () => {
        const plat = flattenTree(ARBRE, new Set([1]));
        expect(plat.map((r) => r.name)).toEqual([
            "Type de Camplate", "Classic", "Ciné", "Formes du drone", "Forme",
        ]);
    });

    test("une valeur se rend au SECOND niveau, son attribut au premier", () => {
        const plat = flattenTree(ARBRE, new Set([1]));
        expect(plat[0].depth).toBe(0);
        expect(plat[1].depth).toBe(1);
    });

    test("⚠️ un attribut SANS valeur ne promet pas de second niveau", () => {
        // Le chevron ne doit pas apparaître : il inviterait à déplier du vide.
        const plat = flattenTree(ARBRE, new Set([2]));
        expect(plat.find((r) => r.id === 2).hasValues).toBe(false);
    });

    test("le bandeau d'étape reste au premier niveau, entre les attributs", () => {
        const plat = flattenTree(ARBRE, new Set([1]));
        const etape = plat.find((r) => r.kind === "step");
        expect(etape.depth).toBe(0);
        expect(plat.indexOf(etape)).toBe(3);
    });

    test("⚠️ un arbre vide ou absent ne casse rien", () => {
        // Le composant appelle `flattenTree` AVANT que le serveur ait répondu.
        expect(flattenTree(undefined, new Set())).toEqual([]);
        expect(flattenTree([], new Set())).toEqual([]);
    });
});
