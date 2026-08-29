/**
 * configurator_tree.test.js — la mise à plat de l'arbre (D-210).
 *
 * ⚠️ Une valeur ne s'affiche QUE si son attribut est déplié. Tout rendre et
 * cacher en CSS ferait payer un produit à trois cents valeurs pour rien — c'est
 * précisément le cas que le dialogue existe pour éviter (D-206).
 */
import {dropIndex, flattenTree, reorder} from "../src/js/configurator_tree.esm.js";

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

describe("Réordonner ne concerne que les lignes d'attribut", () => {
    const IDS = [10, 20, 30];

    test("déplacer une ligne vers le bas la place APRÈS sa cible", () => {
        expect(reorder(IDS, 0, 2)).toEqual([20, 30, 10]);
    });

    test("et vers le haut, avant", () => {
        expect(reorder(IDS, 2, 0)).toEqual([30, 10, 20]);
    });

    test("⚠️ déposer une ligne sur elle-même ne change RIEN", () => {
        // Sans ce cas, un simple clic maintenu réécrirait toutes les séquences —
        // et, l'ordre portant l'appartenance aux étapes (D-202), une écriture
        // inutile n'est jamais anodine ici.
        expect(reorder(IDS, 1, 1)).toEqual(IDS);
    });

    test("⚠️ un dépôt hors de la liste ne perd aucune ligne", () => {
        expect(reorder(IDS, -1, 2)).toEqual(IDS);
        expect(reorder(IDS, 0, -1)).toEqual(IDS);
    });

    test("l'ordre rendu garde TOUTES les lignes", () => {
        expect(reorder(IDS, 0, 2).sort()).toEqual(IDS.slice().sort());
    });
});

describe("Le point de dépôt se lit sur le VOISIN, pas sur un index", () => {
    // ⚠️ Le cœur ne sait dire que « quelle ligne est restée au-dessus » : il
    // promène un fantôme dans le DOM, il ne compte pas.
    const IDS = [10, 20, 30];

    test("sans voisin, on dépose en TÊTE", () => {
        expect(dropIndex(IDS, 2, null)).toBe(0);
    });

    test("descendre après une ligne mène à SA place — la ligne partie libère un cran", () => {
        // 10 descend sous 20 : il ne devient pas 2ᵉ après 20, il PREND sa place.
        expect(dropIndex(IDS, 0, 20)).toBe(1);
        expect(reorder(IDS, 0, dropIndex(IDS, 0, 20))).toEqual([20, 10, 30]);
    });

    test("remonter après une ligne mène JUSTE APRÈS elle", () => {
        expect(dropIndex(IDS, 2, 10)).toBe(1);
        expect(reorder(IDS, 2, dropIndex(IDS, 2, 10))).toEqual([10, 30, 20]);
    });

    test("⚠️ un voisin INCONNU refuse le dépôt — et rien ne bouge", () => {
        // C'est ce qui empêche une valeur de changer d'attribut en glissant :
        // aucun élément du DOM ne les regroupe, le refus se joue ici.
        expect(dropIndex(IDS, 0, 999)).toBe(-1);
        expect(reorder(IDS, 0, dropIndex(IDS, 0, 999))).toEqual(IDS);
    });
});
