/**
 * LA BARRE D'ACTION — D-389 (Gerry, 2026-10-01) : « le footer affiche le prix [et] le bouton
 * d'ajout au panier avec qu'une icône, sur une seule ligne » ; le panier pour TOUS les hôtes,
 * avec l'icône qu'utilise Odoo.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const SRC = join(__dirname, "..", "src", "page");
const XML = readFileSync(join(SRC, "configurator_page.xml"), "utf8").replace(/<!--[\s\S]*?-->/g, " ");
const SCSS = readFileSync(join(SRC, "configurator_page.scss"), "utf8").replace(/\/\*[\s\S]*?\*\//g, " ");

/** Le corps d'un gabarit nommé. */
function template(name) {
    const start = XML.indexOf(`<t t-name="${name}">`);
    expect(start).toBeGreaterThan(-1);
    return XML.slice(start, XML.indexOf("\n</t>", start));
}

describe("la barre d'action", () => {
    const bar = template("product_configurator_web_3d.ActionBar");

    test("le pied de la colonne l'appelle, hors de toute boucle — un seul endroit la décrit (L-453)", () => {
        expect(XML).toMatch(/<div class="o_cfg3d_footer">\s*<t t-call="product_configurator_web_3d.ActionBar"\/>/);
    });

    test("le prix, puis le panier : l'icône d'Odoo, et un NOM pour le lecteur d'écran", () => {
        expect(bar).toContain('class="o_cfg3d_price"');
        expect(bar).toContain('t-esc="price"');
        const button = bar.slice(bar.indexOf("<button"), bar.indexOf("</button>"));
        expect(button).toContain('<i class="fa fa-shopping-cart" role="img"/>');
        expect(button).toContain('t-att-title="confirmLabel"');
        expect(button).toContain('t-att-aria-label="confirmLabel"');
        // L'icône SEULE : plus de libellé écrit dans le bouton.
        expect(button).not.toContain('t-esc="confirmLabel"');
    });

    test("le bouton reste celui qui termine — et disparaît une fois la configuration close", () => {
        expect(bar).toContain('t-on-click="() => this.onConfirm()"');
        expect(bar).toContain('t-if="state.model and !state.model.closed and !state.model.error"');
        expect(bar).not.toMatch(/\bnot\b/);
    });

    test("ⓘ pas de bouton de sauvegarde pour l'instant (Gerry, 2026-10-01)", () => {
        expect((bar.match(/<button/g) || []).length).toBe(1);
    });

    test("UNE ligne : le prix prend la place, le bouton garde la sienne", () => {
        expect(SCSS).toMatch(/\.o_cfg3d_actionbar \{\s*display: flex;\s*align-items: center;/);
        expect(SCSS).toMatch(/\.o_cfg3d_price \{\s*flex: 1 1 auto;\s*min-width: 0;/);
        expect(SCSS).toMatch(/\.o_cfg3d_confirm \{\s*flex: 0 0 auto;/);
        expect(SCSS).not.toMatch(/\.o_cfg3d_confirm \{[^}]*width: 100%/);
    });
});
