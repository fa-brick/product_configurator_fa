/** @odoo-module */
/**
 * website_preview_exit.test.js — La page du configurateur sort de l'aperçu du site (D-540, L-637).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { inOdooFrame, leaveOdooFrame } from "@product_configurator_web_3d/page/website_preview_exit";

/** Une fenêtre factice : dans un cadre ou non, et ce que la fenêtre du haut a reçu. */
function fakeWindow({ framed }) {
    const replaced = [];
    const top = { location: { replace: (url) => replaced.push(url) } };
    const win = {
        frameElement: framed ? {} : null,
        top: framed ? top : null,
        location: { href: "https://shop.test/configurator/abc" },
    };
    if (!framed) win.top = win;
    return { win, replaced };
}

describe("dans l'aperçu du site, la page se recharge dans la fenêtre entière", () => {
    test("un cadre du back-office est reconnu", () => {
        expect(inOdooFrame(fakeWindow({ framed: true }).win)).toBe(true);
        expect(inOdooFrame(fakeWindow({ framed: false }).win)).toBe(false);
    });

    test("la fenêtre du haut prend la même adresse, sans entrée d'historique de plus", () => {
        const { win, replaced } = fakeWindow({ framed: true });
        expect(leaveOdooFrame(win)).toBe(true);
        expect(replaced).toEqual(["https://shop.test/configurator/abc"]);
    });

    test("hors cadre, rien ne bouge", () => {
        const { win, replaced } = fakeWindow({ framed: false });
        expect(leaveOdooFrame(win)).toBe(false);
        expect(replaced).toEqual([]);
    });
});

describe("la fiche ne prépare pas de scène dans l'aperçu", () => {
    const OVERLAY = readFileSync(join(__dirname, "..", "..", "..", "product_configurator_web_sale",
                                      "static", "src", "overlay", "configurator_overlay.js"), "utf8");

    test("le cadre est testé AVANT de détourner le bouton et de préparer", () => {
        const frame = OVERLAY.indexOf("if (inOdooFrame())");
        expect(frame).toBeGreaterThan(-1);
        expect(frame).toBeLessThan(OVERLAY.indexOf("this._bindTrigger();"));
        expect(frame).toBeLessThan(OVERLAY.indexOf("this._prepareWhenIdle();"));
    });

    test("et le lien ouvre la page dans la fenêtre entière", () => {
        expect(OVERLAY).toContain('setAttribute("target", "_top")');
    });
});
