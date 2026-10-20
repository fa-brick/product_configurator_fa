/** @odoo-module */
/**
 * answer_extra_price.test.js — le SUPPLÉMENT de chaque réponse et le TOTAL formaté (W-100, D-396).
 *
 * Les libellés viennent du serveur, déjà formatés : la page les TRANSPORTE (`toViewModel`, liste blanche,
 * [[L-212]]), les MONTRE dans chaque forme, et dit au serveur qu'elle est sur le SITE.
 */
jest.mock("@product_editor/engine/builder/to_buildable", () => new Proxy({}, {
    get: () => class Stub {},
}));

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { session } from "@web/session";
import { splitExtra, toViewModel } from "@product_configurator_web_3d/configurator_state";
import { AnswerList } from "@product_configurator_web_3d/answers/answer_list";
import { ConfiguratorPage, onSite } from "@product_configurator_web_3d/page/configurator_page";

const SRC = join(__dirname, "..", "src");
const XML = readFileSync(join(SRC, "answers", "answers.xml"), "utf8");

/** Le gabarit nommé, de son ouverture à la suivante. */
function template(name) {
    const start = XML.indexOf(`t-name="product_configurator_web_3d.${name}"`);
    const next = XML.indexOf("t-name=", start + 1);
    return XML.slice(start, next === -1 ? undefined : next);
}

/** Une branche de `AnswerList`, de sa condition à la suivante. */
function branch(condition, until) {
    return XML.slice(XML.indexOf(condition), XML.indexOf(until));
}

const SHOWN = '<t t-if="value.extra" t-call="product_configurator_web_3d.ExtraBadge"><t t-set="badge" t-value="value"/></t>';

describe("le supplément traverse la mise en forme", () => {
    const model = toViewModel({
        price: 40.5, total: 40.5, totalLabel: "48,51 €",
        attributes: [{ id: 1, name: "Bottom", values: [
            { id: 10, name: "Light", extra: "+10,00 €" },
            { id: 11, name: "Sans" },
        ] }],
    });

    test("chaque réponse garde son `extra`, `null` quand le serveur n'en donne pas", () => {
        expect(model.questions[0].values.map((v) => v.extra)).toEqual(["+10,00 €", null]);
    });

    test("le signe et le montant, à part — les deux moitiés du badge d'Odoo", () => {
        const [light, none] = model.questions[0].values;
        expect([light.extraSign, light.extraAmount]).toEqual(["+", "10,00 €"]);
        expect([none.extraSign, none.extraAmount]).toEqual([null, null]);
        expect(splitExtra("\u22123,00 €")).toEqual({ extraSign: "\u2212", extraAmount: "3,00 €" });
    });

    test("le total garde son libellé à côté du nombre", () => {
        expect(model.totalLabel).toBe("48,51 €");
        expect(model.total).toBe(40.5);
    });

    test("un serveur ancien, sans libellé : `null`, et la page retombe sur le nombre", () => {
        expect(toViewModel({ price: 3, total: 3 }).totalLabel).toBeNull();
    });
});

describe("le supplément se voit dans chaque forme", () => {
    test("⚠️ le badge est tenu par la PAGE, sans `.badge` ni `text-bg-info` : le même au site et au devis (D-498)", () => {
        const badge = template("ExtraBadge");
        expect(badge).toContain('<span class="o_cfg3d_extra">');
        expect(badge).toContain('class="o_cfg3d_extra_sign" t-esc="badge.extraSign"');
        expect(badge).toContain('class="o_cfg3d_extra_amount" t-esc="badge.extraAmount"');
        expect(badge).not.toMatch(/\bbadge text-bg|text-muted/);
    });

    test("le signe et le montant sont séparés par un `gap`, et le badge rétrécit avec sa carte (D-498)", () => {
        const scss = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.scss"), "utf8");
        const block = scss.match(/\.o_cfg3d_extra \{([\s\S]*?)\n\}/)[1];
        expect(block).toMatch(/display: inline-flex;/);
        expect(block).toMatch(/gap: 0\.3em;/);
        expect(block).toMatch(/border: 1px solid \$info;/);
        expect(scss).toMatch(/\.o_cfg3d_card, \.o_cfg3d_bigswatch \{ container-type: inline-size; \}/);
        expect(scss).toMatch(/@container \(max-width: 76px\) \{/);
    });

    test("la carte, la grande pastille : sous le libellé", () => {
        expect(template("Card")).toContain(SHOWN);
        expect(template("BigSwatch")).toContain(SHOWN);
    });

    test("les boutons et les cases : à côté du nom", () => {
        expect(branch('<div t-else="" class="o_cfg3d_values">', "<!-- ⓘ UNE CARTE")).toContain(SHOWN);
        expect(branch("t-elif=\"question.displayType === 'multi'\"", "<!-- ── RADIO")).toContain(SHOWN);
    });

    test("la ligne résumé : le supplément de la réponse CHOISIE", () => {
        expect(branch("t-if=\"question.answerLayout === 'summary'\"", "<!-- ── LA CARTE"))
            .toContain('<t t-if="picked and picked.extra" t-call="product_configurator_web_3d.ExtraBadge"><t t-set="badge" t-value="picked"/></t>');
    });

    test("la liste du panneau de choix", () => {
        expect(template("AnswerPanel")).toContain(SHOWN);
    });

    test("la couleur et la liste déroulante : dans leur texte, faute de place", () => {
        expect(branch("t-elif=\"question.displayType === 'color'\"", "<!-- ── LA LISTE"))
            .toContain('t-att-title="this.answerTitle(value)"');
        expect(branch("t-elif=\"question.displayType === 'select'\"", "<!-- ── LES CASES"))
            .toContain('t-esc="this.answerTitle(value)"');
    });

    test("`answerTitle` : le nom, et le supplément entre parenthèses s'il existe", () => {
        const { answerTitle } = AnswerList.prototype;
        expect(answerTitle({ name: "Brillant", extra: "+5,00 €" })).toBe("Brillant (+5,00 €)");
        expect(answerTitle({ name: "Mat", extra: null })).toBe("Mat");
    });
});

describe("le total affiché, et le drapeau du site", () => {
    const price = Object.getOwnPropertyDescriptor(ConfiguratorPage.prototype, "price").get;

    test("le libellé d'abord, le nombre nu à défaut", () => {
        expect(price.call({ state: { model: { totalLabel: "48,51 €", total: 40.5 } } })).toBe("48,51 €");
        expect(price.call({ state: { model: { totalLabel: null, total: 40.5 } } })).toBe(40.5);
    });

    test("⚠️ `site` n'est vrai que sur le site : le dialogue du devis reste HT", () => {
        session.is_frontend = true;
        expect(onSite()).toBe(true);
        delete session.is_frontend;
        expect(onSite()).toBe(false);
    });

    test("chaque appel de la page porte `site`", async () => {
        const rpcMock = require("@web/core/network/rpc");
        rpcMock.__reset();
        const page = Object.create(ConfiguratorPage.prototype);
        page.props = { token: "t" };
        page.holder = "me";
        session.is_frontend = true;
        await page._call("/configurator/state");
        delete session.is_frontend;
        await page._call("/configurator/set_value", { value_id: 3 });
        expect(rpcMock.calls.map((call) => call.params.site)).toEqual([true, false]);
        expect(rpcMock.calls[1].params.value_id).toBe(3);
    });
});
