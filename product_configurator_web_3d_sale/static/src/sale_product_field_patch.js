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
import { ConfiguratorDialog } from "@product_configurator_web_3d/configurator_dialog";
import { getLinkedSaleOrderLines } from "@sale/js/sale_utils";
import { uuid } from "@web/views/utils";

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
    async _applyWeb3dConfiguration({ productId, sessionId, separateLines = [] }) {
        if (!productId) return;
        const main = this.props.record;
        await main.update({
            product_id: [productId, main.data.product_template_id[1]],
            config_session_id: [sessionId, ""],
        });
        await this._applySeparateLines(main, separateLines);
    },

    /**
     * Les pièces VENDUES À PART, chacune sur SA ligne rattachée à celle-ci — D-368.
     *
     * ⓘ **Le rattachement du cœur** : une ligne NEUVE n'a pas encore d'identifiant, on la
     * désigne par `virtual_id` / `linked_virtual_id`, que `sale.order.line.create` résout en
     * `linked_line_id` ; une ligne déjà enregistrée se désigne par `linked_line_id`. Supprimer
     * la ligne du produit emporte les siennes (`ondelete` du cœur).
     *
     * ⚠️ **Une reconfiguration REMPLACE les lignes rattachées** plutôt que d'en empiler :
     * elles sont retirées puis reposées. Ce sont celles de la configuration — un produit
     * configurable n'a pas d'autre ligne rattachée par ce chemin.
     *
     * ⚠️ **Côté client, et nulle part ailleurs** : `_web_after_confirm` (serveur) ne crée pas
     * ces lignes, sans quoi reconfigurer une ligne enregistrée les poserait deux fois.
     */
    async _applySeparateLines(main, separateLines) {
        const lines = main.model.root.data.order_line;
        for (const old of getLinkedSaleOrderLines(main)) {
            await lines.delete(old);
        }
        const wanted = (separateLines || []).filter((line) => line.productId);
        if (!wanted.length) return;
        let link;
        if (main.isNew) {
            let virtualId = main.data.virtual_id;
            if (!virtualId) {
                virtualId = uuid();
                await main.update({ virtual_id: virtualId });
            }
            link = { linked_virtual_id: virtualId };
        } else {
            link = { linked_line_id: [main.resId, main.data.name || ""] };
        }
        for (const line of wanted) {
            const record = await lines.addNewRecord({ position: "bottom", mode: "readonly" });
            await record.update({
                product_id: [line.productId, line.name],
                product_uom_qty: line.qty || 1,
                ...link,
            });
        }
    },
});
