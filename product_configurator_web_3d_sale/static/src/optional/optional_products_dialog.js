/** @odoo-module **/
/**
 * Les PRODUITS OPTIONNELS, proposés une fois le produit configuré posé — D-537.
 *
 * ⓘ Le geste d'Odoo pour un produit ordinaire, après coup : la fenêtre de `sale`
 * (`ProductConfiguratorDialog`) affiche et AJOUTE le produit principal, déjà posé ici.
 * ⓘ Une seule fenêtre pour la boutique et le devis : l'hôte dit comment ajouter
 * (`add`), comment configurer (`configure`, sinon le lien de l'optionnel) et ce que
 * porte le pied (`footerLinks`, sinon « Fermer »).
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";

export class OptionalProductsDialog extends Component {
    static template = "product_configurator_web_3d_sale.OptionalProductsDialog";
    static components = { Dialog };
    static props = {
        products: Array,
        add: Function,
        configure: { type: Function, optional: true },
        withQuantity: { type: Boolean, optional: true },
        footerLinks: { type: Array, optional: true },
        close: Function,
    };

    setup() {
        this.state = useState({ added: {}, qty: {}, busy: false });
    }

    quantityOf(product) {
        return this.state.qty[product.id] || 1;
    }

    setQuantity(product, value) {
        this.state.qty[product.id] = value >= 1 ? value : 1;
    }

    async add(product) {
        await this._run(product, () => this.props.add(product, this.quantityOf(product)));
    }

    async configure(product) {
        await this._run(product, () => this.props.configure(product));
    }

    /** Un geste à la fois ; la ligne passe à « Ajouté » quand l'hôte confirme. */
    async _run(product, gesture) {
        this.state.busy = true;
        try {
            if (await gesture()) this.state.added[product.id] = true;
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
    get closeLabel() { return _t("Close"); }
    get quantityLabel() { return _t("Quantity"); }
}
