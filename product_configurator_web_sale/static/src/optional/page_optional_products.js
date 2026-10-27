/** @odoo-module **/
/**
 * Après l'ajout d'un produit configuré au panier : ses PRODUITS OPTIONNELS — D-537.
 *
 * ⓘ Sans optionnel, rien ne change : le panier, comme avant.
 */
import { patch } from "@web/core/utils/patch";
import { browser } from "@web/core/browser/browser";
import { rpc } from "@web/core/network/rpc";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";
import { OptionalProductsDialog } from "./optional_products_dialog";

patch(ConfiguratorPage.prototype, {
    async _afterCart(main) {
        let products = [];
        try {
            products = await rpc("/configurator/optional_products", { token: this.props.token });
        } catch (e) {
            // ⚠️ Une liste perdue n'empêche jamais l'achat : le panier, sans fenêtre.
            console.warn("[configurateur] optionnels illisibles :", e);
        }
        if (!products?.length) {
            return super._afterCart(main);
        }
        // ⓘ Fermer la fenêtre mène au panier, où le produit configuré attend déjà.
        this.env.services.dialog.add(
            OptionalProductsDialog,
            { products, mainLineId: main?.line_id || null },
            { onClose: () => { browser.location.href = "/shop/cart"; } },
        );
    },
});
