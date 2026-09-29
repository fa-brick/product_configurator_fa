/**
 * La GRANDE PASTILLE (demande de Gerry, 2026-09-29) : un disque illustré, son nom dessous, et
 * un choix qui SE VOIT — coche, anneau, nom en gras. Lue dans les sources, comme les autres
 * gardes de gabarit de ce dossier : Jest n'a ni bundle ni OWL.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const SRC = join(__dirname, "..", "src");
const XML = readFileSync(join(SRC, "page", "configurator_page.xml"), "utf8");
const SCSS = readFileSync(join(SRC, "page", "configurator_page.scss"), "utf8");
const bloc = XML.slice(XML.indexOf("question.displayType === 'swatch'"),
                       XML.indexOf("question.displayType === 'color'"));

describe("la grande pastille", () => {
    test("elle a sa branche, AVANT celle de la couleur", () => {
        expect(XML.indexOf("question.displayType === 'swatch'")).toBeGreaterThan(0);
        expect(bloc.length).toBeGreaterThan(0);
    });

    test("le choix se VOIT : classe choisie, coche, et le nom sous le disque", () => {
        expect(bloc).toContain("'o_cfg3d_bigswatch--chosen': value.chosen");
        expect(bloc).toContain("t-if=\"value.chosen and question.swatchMark === 'check'\"");
        expect(bloc).toContain('class="o_cfg3d_bigswatch_label" t-esc="value.name"');
    });

    test("elle répond comme les autres formes — par onAnswer, placement compris", () => {
        expect(bloc).toContain("this.onAnswer(placementNodeId, question.id, value)");
    });

    test("⚠️ l'anneau est une OMBRE dans une marge réservée — un contour se faisait rogner", () => {
        expect(SCSS).toMatch(/\.o_cfg3d_bigswatches--ring \.o_cfg3d_bigswatch--chosen &\s*\{\s*box-shadow:[^}]*\$o-brand-primary/);
        expect(SCSS).toMatch(/\.o_cfg3d_bigswatches\s*\{[^}]*padding:/);
    });

    test("⚠️ la coche OU l'anneau, jamais les deux (Gerry) — la marque vient de l'attribut", () => {
        expect(bloc).toContain("t-att-class=\"'o_cfg3d_bigswatches--' + question.swatchMark\"");
        // L'anneau n'existe que sous `--ring` : aucune autre règle ne le pose sur la pastille choisie.
        const rings = SCSS.match(/0 0 0 4px \$o-brand-primary/g) || [];
        expect(rings.length).toBe(2);                 // la grande (sous --ring) et la petite « Couleur »
    });

    test("⚠️ le SURVOL ne vise que les pastilles non choisies — il masquait l'anneau", () => {
        expect(SCSS).toContain(".o_cfg3d_bigswatch:not(.o_cfg3d_bigswatch--chosen):hover &");
    });

    test("⚠️ la petite pastille « Couleur » : une OMBRE, plus un outline effacé au focus", () => {
        const swatch = SCSS.slice(SCSS.indexOf(".o_cfg3d_swatch {"));
        const chosen = swatch.slice(swatch.indexOf("&--chosen"), swatch.indexOf("&--muted"));
        expect(chosen).toContain("box-shadow");
        expect(chosen).not.toContain("outline:");
    });

    test("le dialogue de vente d'Odoo l'accepte", () => {
        const tolerance = readFileSync(join(SRC, "sale_card_tolerance.js"), "utf8");
        expect(tolerance).toContain('type === "swatch"');
    });
});
