/**
 * cart_link.test.js — La ligne du panier se LIE à sa configuration (W-99 / D-393).
 *
 * ⓘ Le côté serveur est éprouvé en Python (`product_configurator_web_sale`,
 * `test_no_variant_answer.py`) ; ici, que la page envoie bien de quoi lier.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const PAGE = readFileSync(join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");

describe("la mise au panier", () => {
    const i = PAGE.indexOf('rpc("/shop/cart/update_json"');
    const main = PAGE.slice(i, PAGE.indexOf("});", i));

    test("la ligne principale porte le JETON de la configuration", () => {
        expect(main).toContain("config_session_token: this.props.token");
    });

    test("et toutes les réponses « sans variante »", () => {
        expect(main).toContain("no_variant_attribute_value_ids: this.state.model?.noVariantPtavIds");
    });
});
