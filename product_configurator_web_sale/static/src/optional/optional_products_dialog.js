/** @odoo-module **/
/**
 * Les PRODUITS OPTIONNELS, proposés une fois le produit configuré mis au panier — D-537.
 *
 * ⓘ Le geste d'Odoo pour un produit ordinaire, après coup : la fenêtre de `sale`
 * (`ProductConfiguratorDialog`) affiche et AJOUTE le produit principal, déjà au panier ici.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { rpc } from "@web/core/network/rpc";

export class OptionalProductsDialog extends Component {
    static template = "product_configurator_web_sale.OptionalProductsDialog";
    static components = { Dialog };
    static props = {
        products: Array,
        mainLineId: { type: [Number, { value: null }, { value: undefined }], optional: true },
        close: Function,
    };

    setup() {
        this.state = useState({ added: {}, busy: false });
    }

    /** Ajouter un optionnel, RATTACHÉ à la ligne du produit configuré, comme le fait Odoo. */
    async add(product) {
        this.state.busy = true;
        try {
            const added = await rpc("/shop/cart/update_json", {
                product_id: product.productId, add_qty: 1,
                linked_line_id: this.props.mainLineId || undefined,
            });
            if (added?.line_id) this.state.added[product.id] = true;
        } catch (e) {
            console.warn("[configurateur] optionnel refusé :", product.name, e);
        } finally {
            this.state.busy = false;
        }
    }

    get title() { return _t("Add optional products"); }
    get fromLabel() { return _t("From"); }
    get addLabel() { return _t("Add"); }
    get addedLabel() { return _t("Added"); }
    get configureLabel() { return _t("Configure"); }
    get viewLabel() { return _t("View"); }
    get continueLabel() { return _t("Continue Shopping"); }
    get checkoutLabel() { return _t("Proceed to Checkout"); }
}
