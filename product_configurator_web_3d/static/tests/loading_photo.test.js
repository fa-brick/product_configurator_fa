/**
 * L'attente du configurateur — D-566 : la photo dès le premier octet, toute la hauteur, un seul fond,
 * puis un fondu vers la 3D. Lue dans les sources : Jest n'a ni bundle ni OWL.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = join(__dirname, "..", "..");
const SCSS = readFileSync(join(ROOT, "static", "src", "page", "configurator_page.scss"), "utf8");
const XML = readFileSync(join(ROOT, "static", "src", "page", "configurator_page.xml"), "utf8");
const JS = readFileSync(join(ROOT, "static", "src", "page", "configurator_page.js"), "utf8");
const BOOT = readFileSync(join(ROOT, "views", "configurator_page.xml"), "utf8");

describe("le premier instant", () => {
    test("la photo est dans le HTML du serveur, par l'adresse du jeton", () => {
        expect(BOOT).toContain('<img t-attf-src="/configurator/#{token}/image" alt="" loading="eager" fetchpriority="high"/>');
    });

    test("la scène et la colonne de la page, aux mêmes largeurs", () => {
        expect(SCSS).toMatch(/\.o_cfg3d_boot_side \{\s*flex: 0 0 340px;/);
        expect(SCSS).toContain("@media #{$o-cfg3d-low} { flex-basis: $o-cfg3d-side-low; }");
    });
});

describe("la photo d'attente", () => {
    test("⚠️ toute la hauteur, et la même règle aux deux instants", () => {
        expect(SCSS).toMatch(/\.o_cfg3d_loading, \.o_cfg3d_boot_stage \{\s*img \{\s*max-width: 100%;\s*max-height: 100%;/);
        expect(SCSS).not.toContain("max-height: 70%");
    });

    test("un seul fond : la scène, le voile et le premier instant", () => {
        expect(XML).toContain('viewerBg="viewerBg"');
        expect(XML).toContain('t-att-style="stageStyle"');
        expect(SCSS).toMatch(/\.o_cfg3d_boot_stage \{[^}]*background: \$o-cfg3d-stage;/);
    });

    test("la 3D prête, la photo s'efface en fondu puis quitte le DOM", () => {
        expect(XML).toContain('<div t-if="!state.loadingGone" class="o_cfg3d_loading"');
        expect(XML).toContain("'o_cfg3d_loading--done': state.ready");
        expect(XML).toContain('t-on-transitionend="onLoadingFaded"');
        expect(SCSS).toContain("&--done { opacity: 0; pointer-events: none; }");
    });

    test("⚠️ seule la transition du voile le retire — celle d'un enfant remonte aussi", () => {
        expect(JS).toContain("if (ev.target === ev.currentTarget && this.state.ready) this.state.loadingGone = true;");
    });
});
