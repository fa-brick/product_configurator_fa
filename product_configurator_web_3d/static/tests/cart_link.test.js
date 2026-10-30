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

describe("la page met au panier sans hôte qui le lui dise (D-553)", () => {
    const body = (signature) => {
        const start = PAGE.indexOf(signature);
        expect(start).toBeGreaterThan(-1);
        return PAGE.slice(start, PAGE.indexOf("\n    }", start));
    };

    test("l'ajout au panier ne dépend plus de la seule prop de l'overlay", () => {
        const addToCart = body("async _addToCart() {");
        expect(addToCart).toContain("if (!this.goesToCart) return;");
        expect(addToCart).not.toContain("this.props.cart");
    });

    test("l'état de la session en décide aussi, et le bouton le dit", () => {
        expect(body("get goesToCart() {")).toContain("this.props.cart || this.state.model?.cart");
        expect(body("get confirmLabel() {")).toContain("this.goesToCart ?");
    });
});

describe("une configuration rouverte depuis le panier y retourne (D-556)", () => {
    const body = (signature) => {
        const start = PAGE.indexOf(signature);
        expect(start).toBeGreaterThan(-1);
        return PAGE.slice(start, PAGE.indexOf("\n    }\n", start));
    };

    test("elle n'est jamais ajoutée une seconde fois", () => {
        expect(body("get goesToCart() {")).toContain("!this.state.model?.inCart &&");
    });

    test("la confirmer ramène au panier, AVANT tout ajout", () => {
        const addToCart = body("async _addToCart() {");
        const back = addToCart.indexOf('if (this.state.model?.inCart) {\n            browser.location.href = "/shop/cart";');
        expect(back).toBeGreaterThan(-1);
        expect(back).toBeLessThan(addToCart.indexOf('rpc("/shop/cart/update_json"'));
    });
});
