/** @odoo-module */
/**
 * remote_change.test.js — le bus porte un SIGNAL, la page relit l'état ([[L-451]]).
 *
 * ⚠️ Le bus portait tout `web_state()` — environ 500 Ko sur le JeNo — à chaque clic, et
 * l'écho revenait à l'AUTEUR qui venait de recevoir le même état en réponse (mesuré le
 * 2026-09-29 : un second `web_state()` par clic côté serveur, une ligne d'environ 500 Ko
 * dans `bus_bus`). Il ne porte plus que `{author}`.
 */
jest.mock("@product_editor/engine/builder/to_buildable", () => new Proxy({}, {
    get: () => class Stub {},
}));

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";

/** La page sans OWL : chaque lecture attend la porte que le test ouvre. */
function page() {
    const p = Object.create(ConfiguratorPage.prototype);
    p.holder = "me";
    p.reads = [];
    p.applied = [];
    p._call = jest.fn((route) => {
        let open, fail;
        const promise = new Promise((resolve, reject) => { open = resolve; fail = reject; });
        p.reads.push({ route, open, fail });
        return promise;
    });
    p._applyModel = jest.fn(async (payload) => { p.applied.push(payload); });
    return p;
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("un signal du bus — relire, sauf si c'est nous", () => {
    test("⚠️ son PROPRE signal ne relit rien : la réponse du clic a déjà tout apporté", async () => {
        const p = page();
        await p._onRemoteChange({ author: "me" });
        expect(p._call).not.toHaveBeenCalled();
        expect(p._applyModel).not.toHaveBeenCalled();
    });

    test("le signal d'un AUTRE fait relire l'état, et l'applique par le chemin d'un clic", async () => {
        const p = page();
        const done = p._onRemoteChange({ author: "other" });
        await flush();
        expect(p.reads.map((r) => r.route)).toEqual(["/configurator/state"]);
        p.reads[0].open({ rev: 1 });
        await done;
        expect(p.applied).toEqual([{ rev: 1 }]);
    });

    test("un signal SANS auteur — une écriture du backend — fait relire tout le monde", async () => {
        const p = page();
        const done = p._onRemoteChange({ author: null });
        await flush();
        p.reads[0].open({ rev: 1 });
        await done;
        expect(p.applied).toEqual([{ rev: 1 }]);
        const again = p._onRemoteChange(undefined);
        await flush();
        p.reads[1].open({ rev: 2 });
        await again;
        expect(p.applied).toEqual([{ rev: 1 }, { rev: 2 }]);
    });

    test("⚠️ des signaux PENDANT une lecture n'en demandent qu'UNE de plus, après elle", async () => {
        const p = page();
        const done = p._onRemoteChange({ author: "other" });
        await flush();
        await p._onRemoteChange({ author: "other" });
        await p._onRemoteChange({ author: "other" });
        await p._onRemoteChange({ author: "other" });
        expect(p.reads).toHaveLength(1);
        p.reads[0].open({ rev: 1 });
        await flush();
        expect(p.reads).toHaveLength(2);
        p.reads[1].open({ rev: 4 });
        await done;
        // Dans l'ordre : l'état le plus récent est appliqué en DERNIER.
        expect(p.applied).toEqual([{ rev: 1 }, { rev: 4 }]);
        expect(p.reads).toHaveLength(2);
    });

    test("une lecture qui échoue est dite, et ne bloque pas les suivantes", async () => {
        const p = page();
        const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
        const done = p._onRemoteChange({ author: "other" });
        await flush();
        p.reads[0].fail(new Error("offline"));
        await done;
        expect(warn).toHaveBeenCalled();
        const again = p._onRemoteChange({ author: "other" });
        await flush();
        p.reads[1].open({ rev: 2 });
        await again;
        expect(p.applied).toEqual([{ rev: 2 }]);
        warn.mockRestore();
    });
});

describe("⚠️ la page n'applique plus un message du bus comme un état", () => {
    const RAW = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");
    const SOURCE = RAW.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ");

    test("l'abonnement passe par `_onRemoteChange`", () => {
        expect(SOURCE).toContain("const onRemote = (message) => this._onRemoteChange(message);");
        expect(SOURCE).toContain('bus.subscribe("configurator_state", onRemote)');
    });
});
