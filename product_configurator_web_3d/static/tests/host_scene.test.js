/** @odoo-module */
/**
 * host_scene.test.js — La copie de la scène pour un HÔTE qui montre le produit (W-111, 8.4d).
 *
 * Ce qui décide de sa justesse : une copie part après chaque construction, la dernière seule ; une
 * copie dépassée ou arrivée après le démontage est libérée, jamais publiée ; une page qui ne
 * construit rien le dit, pour que l'hôte n'attende pas.
 *
 * ⓘ La page est prise sans OWL : son prototype sur un `this` minimal, comme `scene_publish`.
 */
jest.mock("@product_editor/engine/three/scene_snapshot", () => ({ disposeSnapshot: jest.fn() }));

import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";
import { disposeSnapshot } from "@product_editor/engine/three/scene_snapshot";

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

/** La page, et un viewer dont chaque copie attend qu'on la livre. */
function page(onScene) {
    const p = Object.create(ConfiguratorPage.prototype);
    p.props = { onScene };
    p.pending = [];
    p.onRegisterViewerApi({
        snapshotSolids: () => new Promise((resolve) => p.pending.push(resolve)),
    });
    return p;
}

beforeEach(() => disposeSnapshot.mockClear());

test("la copie d'une construction est publiée à l'hôte, une fois", async () => {
    const onScene = jest.fn();
    const p = page(onScene);
    p._buildTicket = p._snapshotTicket = 1;
    p._publishSnapshot();
    p._publishSnapshot();   // un second rendu ne redemande rien
    expect(p.pending).toHaveLength(1);
    p.pending[0]("copie 1");
    await flush();
    expect(onScene).toHaveBeenCalledWith("copie 1");
});

test("⚠️ une copie DÉPASSÉE par une construction plus récente est libérée, jamais publiée", async () => {
    const onScene = jest.fn();
    const p = page(onScene);
    p._buildTicket = p._snapshotTicket = 1;
    p._publishSnapshot();
    p._buildTicket = 2;     // une réponse a relancé la construction pendant la copie
    p.pending[0]("ancienne");
    await flush();
    expect(onScene).not.toHaveBeenCalled();
    expect(disposeSnapshot).toHaveBeenCalledWith("ancienne");
});

test("⚠️ une copie arrivée après le démontage est libérée", async () => {
    const onScene = jest.fn();
    const p = page(onScene);
    p._buildTicket = p._snapshotTicket = 1;
    p._publishSnapshot();
    p._unmounted = true;
    p.pending[0]("orpheline");
    await flush();
    expect(onScene).not.toHaveBeenCalled();
    expect(disposeSnapshot).toHaveBeenCalledWith("orpheline");
});

test("sans hôte, rien n'est copié ; sans définition, l'hôte apprend qu'il n'y aura rien", async () => {
    const p = page(undefined);
    p.state = { pieces: [], postBuild: {} };
    await p._buildScene({ definition: null });
    p._publishSnapshot();
    expect(p.pending).toHaveLength(0);

    const onScene = jest.fn();
    const host = page(onScene);
    host.state = { pieces: [], postBuild: {} };
    await host._buildScene({ definition: null });
    expect(onScene).toHaveBeenCalledWith(null);
});
