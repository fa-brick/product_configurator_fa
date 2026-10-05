/**
 * free_number_input.test.js — La saisie libre d'un NOMBRE n'a pas de liste (Gerry, 2026-10-05).
 *
 * La question autorise l'ajout : ses valeurs existantes ne sont qu'une partie des réponses
 * possibles, et la déroulante d'`AutoComplete` se posait sur les onglets du téléphone pendant
 * que le pavé numérique se refermait à la frappe ([[L-504]]). Un champ nu, qui appelle le pavé.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const SRC = join(__dirname, "../src/page");
const XML = readFileSync(join(SRC, "configurator_page.xml"), "utf8").replace(/<!--[\s\S]*?-->/g, " ");
const JS = readFileSync(join(SRC, "configurator_page.js"), "utf8");

const free = XML.slice(XML.indexOf('<t t-if="question.free">'), XML.indexOf('class="o_cfg3d_free_unit"'));
const numeric = free.slice(free.indexOf('t-if="question.free.numeric"'), free.indexOf("<AutoComplete"));

describe("saisie libre d'un nombre", () => {
    test("un champ nu, qui appelle le pavé numérique sans manger la virgule (L-218)", () => {
        expect(numeric).toMatch(/^t-if="question\.free\.numeric" type="text" inputmode="decimal"/);
        expect(free).toMatch(/<input t-if="question\.free\.numeric"/);
    });

    test("⚠️ aucune liste de suggestions : ni sources, ni composant à déroulante", () => {
        expect(numeric).not.toContain("sources");
        expect(numeric).not.toContain("AutoComplete");
        expect(JS).not.toContain("NumberAutoComplete");
    });

    test("la réponse part au changement, par la même porte que le texte", () => {
        expect(numeric).toContain('t-on-change="(ev) => this.onFreeChange(placementNodeId, question, ev.target.value)"');
        expect(numeric).toContain('t-att-value="this.freeText(question)"');
    });

    test("le texte libre garde ses suggestions", () => {
        expect(free).toMatch(/<AutoComplete t-else=""[\s\S]*sources="this\.freeSources\(question\)"/);
    });
});
