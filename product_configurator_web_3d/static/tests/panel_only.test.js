/** @odoo-module */
/**
 * panel_only.test.js — La page en PANNEAU SEUL, dans la barre latérale d'un environnement (W-111, 8.4e).
 *
 * Ce qui décide de sa justesse, et qu'aucune erreur ne signalerait : le viewer reste MONTÉ et de
 * taille réelle (c'est lui qui fait la copie remise à l'hôte), la largeur de la fenêtre ne bascule
 * pas la colonne en mode téléphone, et le panier n'y est pas.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const SRC = join(__dirname, "../src/page");
const SCSS = readFileSync(join(SRC, "configurator_page.scss"), "utf8").replace(/\/\*[\s\S]*?\*\//g, " ");
const XML = readFileSync(join(SRC, "configurator_page.xml"), "utf8").replace(/<!--[\s\S]*?-->/g, " ");
const JS = readFileSync(join(SRC, "configurator_page.js"), "utf8");

describe("panneau seul", () => {
    test("⚠️ le viewer est HORS DE L'ÉCRAN, de taille réelle — jamais masqué", () => {
        const block = SCSS.slice(SCSS.indexOf(".o_cfg3d_page--panel {"));
        const viewer = block.slice(block.indexOf(".o_cfg3d_viewer {"), block.indexOf("}"));
        expect(viewer).toMatch(/position: fixed;/);
        expect(viewer).toMatch(/left: -10000px;/);
        expect(viewer).toMatch(/width: 960px;/);
        expect(viewer).toMatch(/height: 720px;/);
        expect(viewer).not.toMatch(/display: none|visibility: hidden/);
    });

    test("la page ne suit ni la largeur de la fenêtre ni le clavier", () => {
        expect(JS).toMatch(/if \(!this\.props\.panelOnly\) \{\s*this\._watchCompact\(\);\s*this\._watchKeyboard\(\);\s*\}/);
    });

    test("la flèche rend la main à l'hôte, à gauche du nom du produit", () => {
        expect(XML).toContain('<button t-if="props.onBack" class="o_cfg3d_backarrow"');
        expect(XML).toContain('t-on-click="() => this.props.onBack()"');
    });
});
