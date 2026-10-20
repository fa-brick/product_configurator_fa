/**
 * LA PAGE CALÉE AU-DESSUS DU CLAVIER — D-389, D-498 : sur téléphone comme sur tablette,
 * le clavier numérique faisait glisser la page vers le haut, et la 3D sortait de l'écran.
 * La page se pose désormais sur la partie VISIBLE (`visualViewport`) pendant une saisie.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";

const SRC = join(__dirname, "..", "src", "page");
const SCSS = readFileSync(join(SRC, "configurator_page.scss"), "utf8").replace(/\/\*[\s\S]*?\*\//g, " ");
const XML = readFileSync(join(SRC, "configurator_page.xml"), "utf8").replace(/<!--[\s\S]*?-->/g, " ");
const JS = readFileSync(join(SRC, "configurator_page.js"), "utf8");

// ⓘ La RÈGLE (quand caler, où) et ses écouteurs vivent dans l'éditeur (`utils/keyboard_fit.js`, D-498) et y sont
// éprouvés ; ici, ce que la PAGE en fait.
describe("la page suit le clavier par la règle de l'éditeur (D-498)", () => {
    test("`_watchKeyboard` passe par `useKeyboardFit`, sur la racine de la page", () => {
        expect(JS).toMatch(/import \{ useKeyboardFit \} from "@product_editor\/utils\/keyboard_fit";/);
        expect(JS).toMatch(/_watchKeyboard\(\) \{\s*this\.keyboard = useKeyboardFit\(\(\) => this\.pageRef\?\.el\);\s*\}/);
    });

    test("⚠️ plus de copie locale de la règle : elle ne doit pas diverger de celle de l'éditeur", () => {
        const state = readFileSync(join(__dirname, "..", "src", "configurator_state.js"), "utf8");
        expect(state).not.toMatch(/export function keyboardFit|export function isTypingField|KEYBOARD_MIN_HEIGHT/);
    });

    test("calée, la page publie la place et la taille ; sinon, rien", () => {
        const page = Object.create(ConfiguratorPage.prototype);
        expect(page.keyboardStyle).toBe("");
        page.keyboard = { fit: { top: 310, height: 480, bottom: 125 } };
        expect(page.keyboardStyle).toBe("--o-cfg3d-visible-top: 310px; --o-cfg3d-visible-height: 480px;");
        page.keyboard = { fit: null };
        expect(page.keyboardStyle).toBe("");
    });
});

describe("le gabarit et le style", () => {
    test("la racine porte la classe et le style du calage", () => {
        expect(XML).toMatch(/<div class="o_cfg3d_page" t-ref="page"\s+t-att-class="\{ 'o_cfg3d_page--keyboard': keyboardFit, 'o_cfg3d_page--panel': props\.panelOnly \}"\s+t-att-style="keyboardStyle">/);
    });

    test("calée, la page est FIXE à la place et à la taille données ; la 3D cède, le titre aussi", () => {
        const block = SCSS.match(/\.o_cfg3d_page--keyboard \{([\s\S]*?)\n\}/);
        expect(block).not.toBe(null);
        expect(block[1]).toMatch(/position: fixed;/);
        expect(block[1]).toMatch(/top: var\(--o-cfg3d-visible-top, 0px\);/);
        expect(block[1]).toMatch(/height: var\(--o-cfg3d-visible-height, 100dvh\);/);
        expect(block[1]).toMatch(/\.o_cfg3d_viewer \{ min-height: 0; \}/);
        expect(block[1]).toMatch(/\.o_cfg3d_title \{ display: none; \}/);
    });
});
