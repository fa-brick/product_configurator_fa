/** @odoo-module */
/**
 * baked_reader.test.js — une pièce cuite se lit UNE fois pour la vie de la page ([[L-449]]).
 *
 * ⚠️ Le défaut ne se voit qu'au chronomètre : « Tête bombée de vis.glb » sert quinze poses
 * du JeNo, et la page le téléchargeait et le décodait quinze fois à CHAQUE permutation
 * (1,7 à 4,9 s par clic), avec un décodeur Draco neuf — quatre workers jamais fermés — à
 * chaque lecture. L'écran, lui, était juste.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createBakedReader } from "@product_configurator_web_3d/configurator_state";

const VIS = { url: "/web/content/9393?access_token=t", attachmentId: 9393, faces: { a: [1] } };

/** Un lecteur de fichiers espion : compte ses appels, rend des volumes par URL. */
function spyReader({ failFirst = false } = {}) {
    const calls = [];
    const read = async (url, faces) => {
        calls.push({ url, faces });
        if (failFirst && calls.length === 1) throw new Error("HTTP 502");
        return [{ nodeId: "v", url }];
    };
    return { calls, read };
}

describe("createBakedReader — un fichier, une lecture", () => {
    test("quinze poses du même fichier n'ouvrent QU'UN téléchargement, et partagent ses volumes", async () => {
        const spy = spyReader();
        const reader = createBakedReader(spy.read);
        const baked = Object.fromEntries(
            Array.from({ length: 15 }, (_, i) => [`c${i}`, { ...VIS }]));
        const loaded = await reader.read(baked);
        expect(spy.calls).toHaveLength(1);
        expect(loaded.size).toBe(15);
        expect(loaded.get("c0").solids).toBe(loaded.get("c14").solids);
    });

    test("⚠️ une reconstruction suivante ne relit RIEN — c'était tout le coût d'une permutation", async () => {
        const spy = spyReader();
        const reader = createBakedReader(spy.read);
        await reader.read({ c1: { ...VIS } });
        // La réponse du serveur est un objet NEUF à chaque clic : l'identité ne sert à rien.
        const again = await reader.read({ c1: { ...VIS, faces: { a: [1] } }, c2: { ...VIS } });
        expect(spy.calls).toHaveLength(1);
        expect(again.size).toBe(2);
    });

    test("un fichier AUTRE — nouvelle cuisson, autre table de faces — se lit", async () => {
        const spy = spyReader();
        const reader = createBakedReader(spy.read);
        await reader.read({ c1: { ...VIS } });
        await reader.read({ c1: { ...VIS, url: "/web/content/9400?access_token=u" } });
        await reader.read({ c1: { ...VIS, faces: { a: [2] } } });
        expect(spy.calls).toHaveLength(3);
        expect(reader.size).toBe(3);
    });

    test("l'URL à jeton est lue telle quelle ; l'identifiant nu n'est qu'un repli", async () => {
        const spy = spyReader();
        const reader = createBakedReader(spy.read);
        await reader.read({ c1: { ...VIS }, c2: { attachmentId: 77 } });
        expect(spy.calls.map((c) => c.url).sort())
            .toEqual(["/web/content/77", "/web/content/9393?access_token=t"]);
        expect(spy.calls.find((c) => c.url.startsWith("/web/content/9393")).faces).toEqual({ a: [1] });
    });

    test("un échec est DIT, la pose manque, et il n'est PAS mémorisé — le tour suivant retente (L-323)", async () => {
        const spy = spyReader({ failFirst: true });
        const errors = [];
        const reader = createBakedReader(spy.read, { onError: (id, e) => errors.push([id, e.message]) });
        const first = await reader.read({ c1: { ...VIS } });
        expect(first.size).toBe(0);
        expect(errors).toEqual([["c1", "HTTP 502"]]);
        const second = await reader.read({ c1: { ...VIS } });
        expect(second.size).toBe(1);
        expect(spy.calls).toHaveLength(2);
    });

    test("un fichier sans volume ne pose rien — le moteur construit la pièce", async () => {
        const reader = createBakedReader(async () => []);
        expect((await reader.read({ c1: { ...VIS } })).size).toBe(0);
        expect((await reader.read(null)).size).toBe(0);
    });
});

describe("la page — un décodeur Draco, libéré au démontage", () => {
    const RAW = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");
    const SOURCE = RAW.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ");

    test("les cuissons passent par le lecteur partagé", () => {
        expect(SOURCE).toContain("this._bakedReader = createBakedReader(");
        expect(SOURCE).toContain("return this._bakedReader.read(baked)");
    });

    test("⚠️ le décodeur est créé UNE fois — `new DRACOLoader()` n'apparaît que sous garde", () => {
        const matches = SOURCE.match(/new DRACOLoader\(\)/g) || [];
        expect(matches).toHaveLength(1);
        expect(SOURCE).toMatch(/this\._dracoDecoder = this\._dracoDecoder\s*\|\|\s*new DRACOLoader\(\)/);
    });

    test("ses workers s'arrêtent avec la page", () => {
        const unmount = SOURCE.slice(SOURCE.indexOf("onWillUnmount(() => {"));
        expect(unmount.slice(0, 1200)).toContain("this._dracoDecoder?.dispose()");
    });
});
