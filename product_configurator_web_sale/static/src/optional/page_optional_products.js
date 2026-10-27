/** @odoo-module **/
/**
 * Après l'ajout d'un produit configuré au panier : ses PRODUITS OPTIONNELS — D-537.
 *
 * ⓘ Sans optionnel, rien ne change : le panier, comme avant.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { rpc } from "@web/core/network/rpc";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";
import { OptionalProductsDialog } from "@product_configurator_web_3d_sale/optional/optional_products_dialog";

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
        this.env.services.dialog.add(
            OptionalProductsDialog,
            {
                products,
                // ⓘ Rattaché à la ligne du produit configuré, comme Odoo rattache ses optionnels.
                add: async (product) => {
                    const added = await rpc("/shop/cart/update_json", {
                        product_id: product.productId, add_qty: 1,
                        linked_line_id: main?.line_id || undefined,
                    });
                    return !!added?.line_id;
                },
                footerLinks: [
                    { label: _t("Continue Shopping"), href: "/shop" },
                    { label: _t("Proceed to Checkout"), href: "/shop/cart", primary: true },
                ],
            },
            // ⓘ Fermer la fenêtre mène au panier, où le produit configuré attend déjà.
            { onClose: () => { browser.location.href = "/shop/cart"; } },
        );
    },
});
