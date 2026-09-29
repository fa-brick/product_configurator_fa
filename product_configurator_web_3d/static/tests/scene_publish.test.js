/** @odoo-module */
/**
 * scene_publish.test.js — une permutation publie ses POSES et ses MATIÈRES ensemble ([[L-449]]).
 *
 * ⚠️ **Le défaut ne se voit qu'à l'INSTANT.** Après une permutation, les zones de la nouvelle
 * pièce arrivaient avec la réponse du serveur, et les poses une à cinq secondes plus tard :
 * le viewer redessinait l'ANCIENNE pièce sans ses zones, au neutre violet (Gerry,
 * 2026-09-29). L'état final, lui, était juste : un test d'état final ne l'aurait pas vu.
 * On rend donc la lecture des fichiers pilotable (une promesse résolue à la main) et on
 * relève ce que la page montre PENDANT.
 *
 * ⓘ La page est prise sans OWL : son prototype sur un `this` minimal. Le moteur est un
 * bouchon qui rend les poses écrites dans la définition.
 */
jest.mock("@product_editor/engine/builder/to_buildable", () => new Proxy({}, {
    get: (_, key) => {
        if (key === "toBuildable") return (definition) => definition;
        if (key === "createChronicle") return () => ({ snapshot: () => ({}) });
        if (key === "projectSketchItems") return (definition) => [definition.id];
        if (key === "subtreeOf") return (pieces, keys) => new Set(keys);
        return class Stub {};
    },
}));

import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";
import { toViewModel } from "@product_configurator_web_3d/configurator_state";

/** Une porte : la promesse que le test ouvre quand il veut. */
function gate() {
    let open;
    const promise = new Promise((resolve) => { open = resolve; });
    return { promise, open };
}

/** Une réponse du serveur : la Cam plate `plate`, de couleur `color`. */
function payload(plate, color = "noir") {
    return {
        state: "draft",
        definition: { id: "m1", model3dId: 1, pieces: [{ key: `c-${plate}` }] },
        scope: { plate },
        zones: { zonesByPiece: { [plate]: [{ id: 1, material: { name: color } }] }, byNode: {} },
    };
}

/** La page sans OWL, dont la lecture des cuissons attend les portes qu'on lui donne. */
function page() {
    const p = Object.create(ConfiguratorPage.prototype);
    p.state = {
        model: null, sceneModel: null, pieces: [], sceneSerial: 0, ready: false,
        postBuild: {}, selection: { nodeId: null, isolated: false }, cameraApply: null,
    };
    p._memos = { selectable: null, selected: null, isolated: null, items: null };
    p.gates = [];
    p._loadBaked = () => {
        const g = gate();
        p.gates.push(g);
        return g.promise.then(() => new Map());
    };
    p._loadImported = async () => null;
    p._session = {
        prepare: async () => {},
        build: (buildable) => ({
            worlds: new Map(), solids: new Map(), baked: new Map(),
            pieces: buildable.pieces, postBuild: {},
        }),
    };
    return p;
}

/**
 * Un RENDU : OWL lit les props du gabarit sur un contexte qui hérite du composant — neuf à
 * chaque rendu, et ici sur deux étages comme sur la page réelle (mesuré le 2026-09-29,
 * [[L-384]]). Un mémo écrit sur `this` y meurt avec le contexte.
 */
const render = (p) => Object.create(Object.create(p));

/** Ce que le viewer reçoit : les poses, et les pièces dont il a les zones. */
const shown = (p) => ({
    pieces: p.state.pieces.map((x) => x.key),
    zones: Object.keys(p.zonesByPiece),
});

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

async function opened(plate = 39569) {
    const p = page();
    p.state.model = p.state.sceneModel = toViewModel(payload(plate));
    const build = p._buildScene(p.state.model);
    await flush();
    p.gates.shift().open();
    await build;
    return p;
}

describe("une permutation — la scène ne change qu'une fois construite", () => {
    test("⚠️ PENDANT le calcul, l'ancienne pièce garde SES zones — jamais le neutre violet", async () => {
        const p = await opened(39569);
        expect(shown(p)).toEqual({ pieces: ["c-39569"], zones: ["39569"] });
        const applying = p._applyModel(payload(39571));
        await flush();
        // La réponse est là, les questions la montrent — la 3D, pas encore.
        expect(p.state.model.scope).toEqual({ plate: 39571 });
        expect(shown(p)).toEqual({ pieces: ["c-39569"], zones: ["39569"] });
        p.gates.shift().open();
        await applying;
        expect(shown(p)).toEqual({ pieces: ["c-39571"], zones: ["39571"] });
    });

    test("⚠️ l'ÉCHO du bus arrivé pendant le calcul ne republie pas les zones sur les anciennes poses", async () => {
        const p = await opened(39569);
        const applying = p._applyModel(payload(39571));
        await flush();
        // Même recette, mêmes valeurs que la réponse : pas de seconde construction…
        await p._applyModel(payload(39571));
        expect(p.gates).toHaveLength(1);
        // …et pas de publication non plus tant que la première n'a pas fini.
        expect(shown(p)).toEqual({ pieces: ["c-39569"], zones: ["39569"] });
        p.gates.shift().open();
        await applying;
        expect(shown(p)).toEqual({ pieces: ["c-39571"], zones: ["39571"] });
    });

    test("une COULEUR, sans construction en cours, se montre tout de suite", async () => {
        const p = await opened(39569);
        await p._applyModel(payload(39569, "bleu"));
        expect(p.gates).toHaveLength(0);
        expect(p.zonesByPiece[39569][0].material.name).toBe("bleu");
    });

    test("⚠️ une construction DÉPASSÉE ne publie rien — la plus récente seule a la main", async () => {
        const p = await opened(39569);
        const first = p._applyModel(payload(39571));
        await flush();
        const second = p._applyModel(payload(39572));
        await flush();
        expect(p.gates).toHaveLength(2);
        // La seconde finit d'abord, la première ensuite : c'est la seconde qui reste.
        p.gates[1].open();
        await second;
        p.gates[0].open();
        await first;
        expect(shown(p)).toEqual({ pieces: ["c-39572"], zones: ["39572"] });
        expect(p.state.sceneModel.scope).toEqual({ plate: 39572 });
    });

    test("la projection de la racine suit la scène, pas les questions", async () => {
        const p = await opened(39569);
        expect(p.rootNodeId).toBe("m1");
        const applying = p._applyModel({ ...payload(39571),
                                         definition: { id: "m2", model3dId: 2, pieces: [] } });
        await flush();
        expect(p.rootNodeId).toBe("m1");
        expect(p.rootPieceId).toBe(1);
        p.gates.shift().open();
        await applying;
        expect(p.rootNodeId).toBe("m2");
    });
});

describe("ce que le viewer compare par IDENTITÉ ne change pas sans raison (L-449)", () => {
    // Le viewer reconstruit TOUTE la scène quand `sketchItems`, `pieces` ou les zones
    // changent de référence. Mesuré le 2026-09-29 : cinq reconstructions par permutation,
    // une seule utile — le passage de `loading`, puis l'écho du bus, refaisaient tout.

    test("⚠️ deux RENDUS sans changement rendent la MÊME projection — chacun sur son contexte", async () => {
        const p = await opened(39569);
        expect(render(p).sketchItems).toBe(render(p).sketchItems);
        expect(render(p).viewerSketchItems).toBe(render(p).sketchItems);
    });

    test("⚠️ les trois autres mémos tiennent aussi d'un rendu à l'autre", async () => {
        const p = await opened(39569);
        expect(render(p).selectableNodeIds).toBe(render(p).selectableNodeIds);
        p.state.selection = { nodeId: "c-39569", isolated: true };
        expect(render(p).selectedNodeIds).toBe(render(p).selectedNodeIds);
        // Isolée, une liste neuve à chaque rendu reconstruisait toute la scène à chaque rendu.
        expect(render(p).viewerPieces).toBe(render(p).viewerPieces);
        expect(render(p).viewerPieces.map((x) => x.key)).toEqual(["c-39569"]);
    });

    test("⚠️ l'ÉCHO du bus — la même réponse, reçue une seconde fois — ne change aucune référence", async () => {
        const p = await opened(39569);
        const before = { items: render(p).sketchItems, zones: p.zonesByPiece, layer: p.zoneMaterialsByNode };
        await p._applyModel(payload(39569));
        expect(p.gates).toHaveLength(0);
        expect(render(p).sketchItems).toBe(before.items);
        expect(p.zonesByPiece).toBe(before.zones);
        expect(p.zoneMaterialsByNode).toBe(before.layer);
    });

    test("une permutation, elle, change la projection — une fois construite", async () => {
        const p = await opened(39569);
        const before = render(p).sketchItems;
        const applying = p._applyModel({ ...payload(39571), scope: { plate: 39571, x: 1 } });
        await flush();
        expect(render(p).sketchItems).toBe(before);
        p.gates.shift().open();
        await applying;
        expect(render(p).sketchItems).not.toBe(before);
    });

    test("isolée, la racine ne se dessine pas — et le vide est TOUJOURS le même", async () => {
        const p = await opened(39569);
        p.state.selection = { nodeId: "c-39569", isolated: true };
        expect(render(p).viewerSketchItems).toEqual([]);
        expect(render(p).viewerSketchItems).toBe(render(p).viewerSketchItems);
    });
});

describe("⚠️ aucun getter de la page n'écrit sur `this` (L-384, L-449)", () => {
    // Lu pendant le rendu, un getter s'exécute sur le contexte du gabarit : l'écriture y
    // reste. Les mémos se rangent dans `this._memos`, créé au `setup()`.
    const { readFileSync } = require("node:fs");
    const { join } = require("node:path");
    const RAW = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");
    const SOURCE = RAW.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ");

    test("aucune affectation `this._x =` dans un corps de getter", () => {
        const offenders = [];
        const re = /\n    get (\w+)\(\) \{([\s\S]*?)\n    \}/g;
        let m;
        while ((m = re.exec(SOURCE))) {
            if (/this\.[\w$]+\s*=[^=]/.test(m[2])) offenders.push(m[1]);
        }
        expect(offenders).toEqual([]);
    });

    test("les mémos naissent dans `setup()`", () => {
        const setup = SOURCE.slice(SOURCE.indexOf("setup() {"), SOURCE.indexOf("_listenToOthers() {"));
        expect(setup).toContain("this._memos = {");
    });
});
