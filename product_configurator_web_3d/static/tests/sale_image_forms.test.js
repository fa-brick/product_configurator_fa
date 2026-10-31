/**
 * La carte, la grande pastille et la couleur illustrée hors de la page du configurateur — D-563.
 * Lue dans les sources, comme les autres gardes de gabarit de ce dossier : Jest n'a ni bundle ni OWL.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const SRC = join(__dirname, "..", "src");
const XML = readFileSync(join(SRC, "sale_image_forms.xml"), "utf8");
const JS = readFileSync(join(SRC, "sale_card_tolerance.js"), "utf8");
const SCSS = readFileSync(join(SRC, "page", "configurator_page.scss"), "utf8");
const block = (name) => XML.slice(XML.indexOf(`t-name="${name}"`), XML.indexOf("</t>\n\n", XML.indexOf(`t-name="${name}"`)));

describe("le dialogue de vente dessine les formes du configurateur", () => {
    test("chaque forme à image a son gabarit, et le switch du cœur garde son repli", () => {
        expect(JS).toContain('card: "product_configurator_web_3d.ptav_card"');
        expect(JS).toContain('swatch: "product_configurator_web_3d.ptav_swatch"');
        expect(JS).toContain('|| "sale.ptav_pills"');
    });

    test("⚠️ les clés servies par le contrôleur sont déclarées au shape — OWL refuse une clé inconnue", () => {
        expect(JS).toMatch(/swatch_mark: \{ type: String, optional: true \}/);
        expect(JS).toMatch(/answer_size: \{ type: String, optional: true \}/);
        expect(JS).toMatch(/preview: \{ type: \[Boolean, String\], optional: true \}/);
    });

    test("la carte et la grande pastille reprennent les classes de la page", () => {
        expect(block("product_configurator_web_3d.ptav_card")).toContain('class="o_cfg3d_card"');
        expect(block("product_configurator_web_3d.ptav_card")).toContain('class="o_cfg3d_card_label"');
        const swatch = block("product_configurator_web_3d.ptav_swatch");
        expect(swatch).toContain('class="o_cfg3d_bigswatch"');
        expect(swatch).toContain('class="o_cfg3d_bigswatch_disc"');
        expect(swatch).toContain("this.props.attribute.swatch_mark !== 'ring'");
    });

    test("⚠️ un libellé autour du bouton radio : le cœur y pose `css_not_available`", () => {
        for (const name of ["product_configurator_web_3d.ptav_card", "product_configurator_web_3d.ptav_swatch"]) {
            const form = block(name);
            expect(form).toMatch(/<label t-foreach="this\.props\.attribute_values"/);
            expect(form).toContain("'css_not_available': ptav.excluded");
            expect(form).toContain('t-call="product_configurator_web_3d.ptav_input"');
        }
        expect(block("product_configurator_web_3d.ptav_input")).toContain('t-on-change="updateSelectedPTAV"');
    });

    test("⚠️ la couleur lit la vignette de la valeur, et garde l'image posée si la vignette manque", () => {
        expect(XML).toContain('t-inherit="sale.ptav_color"');
        expect(XML).toMatch(/ptav\.preview \? 'background:url\(' \+ ptav\.preview/);
        expect(XML).toContain("/web/image/product.template.attribute.value/");
    });
});

describe("la feuille de la page sert aussi la boutique et le dialogue", () => {
    test("le choix se lit sur le bouton radio coché, à côté de la classe de la page", () => {
        expect(SCSS).toContain("&--chosen, &:has(> input:checked) { border-color: $primary;");
        expect(SCSS).toContain(".o_cfg3d_bigswatches--ring .o_cfg3d_bigswatch:has(> input:checked) &,");
        expect(SCSS).toContain(".o_cfg3d_bigswatch:has(> input:checked) & { font-weight: 600; }");
    });

    test("⚠️ la coche n'apparaît que sur la réponse cochée — elle est rendue pour toutes", () => {
        expect(SCSS).toContain(".o_cfg3d_bigswatch:has(> input:not(:checked)) & { display: none; }");
    });

    test("une réponse exclue par Odoo s'éteint comme une réponse éteinte de la page", () => {
        expect((SCSS.match(/&--muted, &\.css_not_available \{ opacity: 0\.4; \}/g) || []).length).toBe(2);
    });

    test("⚠️ le bouton radio est caché : la réponse atteinte au clavier garde un contour", () => {
        expect(SCSS).toContain(".o_cfg3d_bigswatch:has(> input:focus-visible) { outline:");
    });
});
