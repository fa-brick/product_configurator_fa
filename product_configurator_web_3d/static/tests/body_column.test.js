/**
 * body_column.test.js — La page publique tient dans l'écran, bandeau d'une base neutralisée compris (D-498).
 *
 * ⓘ Le bandeau (`web.neutralize_banner`) s'ajoute EN FLUX à la fin du corps : une page haute de `100dvh`
 * faisait déborder le document de sa hauteur, d'où une seconde barre de défilement.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const VIEW = readFileSync(join(__dirname, "..", "..", "views", "configurator_page.xml"), "utf8");
const SCSS = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.scss"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ").replace(/\/\/[^\n]*/g, " ");

describe("le corps de la page publique est une colonne de la hauteur de l'écran", () => {
    test("le gabarit pose la classe du corps", () => {
        expect(VIEW).toContain(`<t t-set="body_classname" t-value="'o_cfg3d_body'"/>`);
    });

    test("le corps ne défile pas, et la page prend ce que le reste laisse", () => {
        const block = SCSS.match(/body\.o_cfg3d_body \{([\s\S]*?)\n\}/);
        expect(block).not.toBe(null);
        expect(block[1]).toMatch(/display: flex;/);
        expect(block[1]).toMatch(/flex-direction: column;/);
        expect(block[1]).toMatch(/height: 100dvh;/);
        expect(block[1]).toMatch(/overflow: hidden;/);
        expect(block[1]).toMatch(/> #wrapwrap \{ flex: 1 1 auto; min-height: 0; \}/);
    });

    test("⚠️ la page CALÉE au-dessus du clavier garde sa propre hauteur", () => {
        expect(SCSS).toMatch(/\.o_cfg3d_page:not\(\.o_cfg3d_page--keyboard\) \{ height: 100%; \}/);
    });
});
