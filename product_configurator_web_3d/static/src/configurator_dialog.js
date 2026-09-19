/** @odoo-module **/
/**
 * Le configurateur 3D DANS le back-office — D-259.
 *
 * ⚠️ **Ce fichier ne dessine rien.** Tout ce qu'il affiche est
 * `ConfiguratorPage`, le composant de la page publique, monté tel quel dans un
 * dialogue du web. C'est la condition posée par Gerry : ce qu'on change pour le
 * client se voit au back-office le jour même, parce que c'est le même code.
 *
 * ⓘ **Il ne connaît NI le devis NI l'ordre de fabrication.** Ses props sont un
 * jeton, un état, une session, un nom — et `onConfirmed`, que l'hôte remplit
 * comme il l'entend. C'est ce qui lui permet de servir les deux, et c'est
 * pourquoi il a quitté le module du devis le 2026-09-19.
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
