/** @odoo-module */
/**
 * root_scope.test.js — Les esquisses de la RACINE se projettent sur sa portée RÉSOLUE (L-547).
 *
 * ⚠️ Le défaut était muet : une racine dont la variable `largeur` vaut `__attribute_16` dessinait
 * ses esquisses sur la portée des seuls attributs — `largeur` y manquait, chaque cote qui la citait
 * retombait sur son défaut. La porte de la sonde W-111 montrait sa poignée à x = 0 au lieu du milieu.
 *
 * ⓘ La page est prise sans OWL ; le moteur est un bouchon dont la projection rend la portée reçue.
 */
jest.mock("@product_editor/engine/builder/to_buildable", () => new Proxy({}, {
    get: (_, key) => {
        if (key === "toBuildable") return (definition) => definition;
        if (key === "createChronicle") return () => ({ snapshot: () => ({}) });
        if (key === "projectSketchItems") return (definition, scope) => [scope];
        return class Stub {};
    },
}));

import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";

function page(rootScope) {
    const p = Object.create(ConfiguratorPage.prototype);
    p.props = {};
    p.state = { model: null, sceneModel: null, pieces: [], sceneSerial: 0, ready: false, postBuild: {},
                selection: { nodeId: null, isolated: false } };
    p._memos = { selectable: null, selected: null, isolated: null, items: null };
    p._loadBaked = async () => new Map();
    p._loadImported = async () => null;
    p._session = {
        prepare: async () => {},
        build: () => ({ tree: { scope: rootScope }, worlds: new Map(), solids: new Map(), baked: new Map(),
                        pieces: [], postBuild: {} }),
    };
    return p;
}

const MODEL = { definition: { id: "m1" }, scope: { __attribute_16: 2400 } };

test("avant toute construction, la portée des attributs ; après, celle de la racine RÉSOLUE", async () => {
    const p = page({ __attribute_16: 2400, largeur: 2400 });
    p.state.sceneModel = MODEL;
    expect(p.sketchItems[0]).toEqual({ __attribute_16: 2400 });
    await p._buildScene(MODEL);
    expect(p.sketchItems[0]).toEqual({ __attribute_16: 2400, largeur: 2400 });
});

test("une construction sans arbre (moteur absent) garde la portée des attributs", async () => {
    const p = page(undefined);
    p._session.build = () => ({ worlds: new Map(), solids: new Map(), baked: new Map(), pieces: [], postBuild: {} });
    await p._buildScene(MODEL);
    expect(p.sketchItems[0]).toEqual({ __attribute_16: 2400 });
});
