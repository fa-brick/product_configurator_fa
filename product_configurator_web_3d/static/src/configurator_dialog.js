/** @odoo-module **/
/**
 * Le configurateur 3D DANS le back-office — D-259.
 *
 * ⚠️ **Ce fichier ne dessine rien** : il monte `ConfiguratorPage` tel quel — un second
 * rendu divergerait de la page publique (D-259).
 *
 * ⚠️ **Il ne connaît NI le devis NI l'ordre de fabrication** : l'hôte remplit
 * `onConfirmed`, sinon le dialogue ne pourrait plus servir les deux.
 */
import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";

export class ConfiguratorDialog extends Component {
    static template = "product_configurator_web_3d.ConfiguratorDialog";
    static components = { Dialog, ConfiguratorPage };
    static props = {
        token: { type: String },
        initialState: { type: Object, optional: true },
        sessionId: { type: Number },
        productName: { type: String, optional: true },
        // Ce que l'hôte fait de la configuration terminée — poser la variante
        // sur sa ligne, ici.
        onConfirmed: { type: Function },
        close: { type: Function },
    };

    get title() {
        return this.props.productName || _t("Configure the product");
    }

    /**
     * ⚠️ On rend la SESSION en plus de la variante. La ligne a besoin des deux :
     * le produit pour se nommer, la session pour que son prix suive
     * (`_compute_price_unit` lit `config_session_id.price`) et pour se rouvrir.
     */
    onPageConfirmed(result) {
        this.props.onConfirmed({ ...result, sessionId: this.props.sessionId });
        this.props.close();
    }
}
