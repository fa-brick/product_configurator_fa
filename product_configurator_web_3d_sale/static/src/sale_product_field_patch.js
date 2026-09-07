/** @odoo-module **/
/**
 * Un produit CONFIGURABLE ouvre NOTRE configurateur — D-259.
 *
 * ⚠️ **Le point d'accroche est celui d'Odoo, pas un nouveau bouton.** Choisir un
 * produit sur une ligne de devis appelle `_openProductConfigurator()` dès qu'il
 * n'a pas de variante unique. On s'y branche : produit `config_ok` → notre
 * dialogue ; tout le reste → celui d'Odoo, intact.
 *
 * ⓘ **Pourquoi pas l'assistant OCA.** Il fabrique une vue formulaire à la volée,
 * champ par champ, et n'a qu'un seul rattachement de widget (`custom_type ==
 * "color"`, avec un `# TODO: Add a field2widget mapper` resté en l'état). Il
 * ignore `display_type` : ni carte, ni pastilles, ni nuancier. Tout ce qu'on
 * ajoute à la page lui reste invisible — c'est la duplication que ce correctif
 * supprime.
 */
import { patch } from "@web/core/utils/patch";
import { SaleOrderLineProductField } from "@sale/js/sale_product_field";
import { ConfiguratorDialog } from "./configurator_dialog";

patch(SaleOrderLineProductField.prototype, {
    /**
     * Le bouton de RECONFIGURATION doit exister pour nos produits aussi.
     *
     * ⚠️ Odoo ne le montre que si le modèle a « des attributs configurables » —
     * des attributs dynamiques, ou au moins deux valeurs quelque part. Un produit
     * configurable dont chaque question n'a qu'UNE réponse aujourd'hui n'en a
     * donc aucun, et le commercial n'aurait aucun moyen de rouvrir sa
     * configuration. Notre `config_ok` suffit à le décider.
     */
    get isConfigurableTemplate() {
        return super.isConfigurableTemplate || !!this.props.record.data.product_tmpl_config_ok;
    },

    /**
     * ⚠️ `product_tmpl_config_ok` suit le MODÈLE, pas la variante : pour un
     * produit configurable, la variante n'existe pas encore au moment du choix,
     * et le `config_ok` de la ligne vaudrait `false` juste quand il compte.
     */
    async _openProductConfigurator(edit = false) {
        const line = this.props.record.data;
        if (!line.product_tmpl_config_ok) {
            return super._openProductConfigurator(...arguments);
        }
        const opened = await this.orm.call(
            "product.template", "web3d_open_configuration",
            [line.product_template_id[0]],
            // ⓘ On REPREND la configuration de la ligne quand elle en a une —
            // rouvrir doit montrer ce qu'on avait répondu, pas une page neuve.
            { session_id: (line.config_session_id && line.config_session_id[0]) || false },
        );
        this.dialog.add(ConfiguratorDialog, {
            token: opened.token,
            initialState: opened.state,
            sessionId: opened.sessionId,
            productName: line.product_template_id[1],
            onConfirmed: (result) => this._applyWeb3dConfiguration(result),
        });
    },

    /**
     * Poser sur la ligne ce que la configuration a produit.
     *
     * ⓘ Écrire `product_id` et `config_session_id` SUFFIT : le nom, les taxes et
     * l'unité se recalculent, et le prix suit `config_session_id.price` par
     * `_compute_price_unit`. La ligne n'est pas encore enregistrée — c'est le
     * devis qui la portera, comme pour n'importe quel produit.
     */
    async _applyWeb3dConfiguration({ productId, sessionId }) {
        if (!productId) return;
        await this.props.record.update({
            product_id: [productId, this.props.record.data.product_template_id[1]],
            config_session_id: [sessionId, ""],
        });
    },
});
