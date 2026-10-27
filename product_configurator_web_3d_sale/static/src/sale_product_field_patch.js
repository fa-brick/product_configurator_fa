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
import { serializeDateTime } from "@web/core/l10n/dates";
import { OptionalProductsDialog } from "@product_configurator_web_3d_sale/optional/optional_products_dialog";

patch(SaleOrderLineProductField.prototype, {
    /**
     * Le bouton de RECONFIGURATION doit exister pour nos produits aussi.
     *
     * ⚠️ Odoo ne le montre que si le modèle a « des attributs configurables » —
     * des attributs dynamiques, ou au moins deux valeurs quelque part. Un produit
     * configurable dont chaque question n'a qu'UNE réponse aujourd'hui n'en a
     * donc aucun, et le commercial n'aurait aucun moyen de rouvrir sa
     * configuration. Le `config_ok` du modèle suffit à le décider.
     */
    get isConfigurableTemplate() {
        return super.isConfigurableTemplate || !!this.props.record.data.product_tmpl_config_ok;
    },

    /**
     * ⚠️ `product_tmpl_config_ok` suit le MODÈLE, pas la variante : pour un
     * produit configurable, la variante n'existe pas encore au moment du choix,
     * et un drapeau lu sur la variante vaudrait `false` juste quand il compte.
     */
    async _openProductConfigurator(edit = false) {
        const line = this.props.record.data;
        if (!line.product_tmpl_config_ok) {
            return super._openProductConfigurator(...arguments);
        }
        const opened = await this.orm.call(
            "product.template", "web3d_open_configuration",
            [line.product_template_id[0]],
            {
                // ⓘ On REPREND la configuration de la ligne quand elle en a une —
                // rouvrir doit montrer ce qu'on avait répondu, pas une page neuve.
                session_id: (line.config_session_id && line.config_session_id[0]) || false,
                // ⚠️ Sans eux, la fenêtre chiffre à la liste du commercial et la ligne à
                // celle du devis : deux prix pour une configuration (D-537).
                ...this._orderPricing(),
            },
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
     * l'unité se recalculent, et le prix suit la session par
     * `_compute_price_unit`. La ligne n'est pas encore enregistrée — c'est le
     * devis qui la portera, comme pour n'importe quel produit.
     */
    async _applyWeb3dConfiguration({ productId, sessionId, separateLines = [] }) {
        if (!productId) return;
        const main = this.props.record;
        const isNew = !main.data.config_session_id;
        await main.update({
            product_id: [productId, main.data.product_template_id[1]],
            config_session_id: [sessionId, ""],
        });
        const options = await this.orm.call(
            "product.template", "web3d_optional_products",
            [main.data.product_template_id[0]], this._orderPricing(),
        );
        await this._applySeparateLines(main, separateLines, options.map((option) => option.id));
        // ⓘ D-537 — les optionnels se proposent à l'AJOUT du produit, pas à chaque correction.
        if (isNew && options.length) {
            this._offerOptionalProducts(main, options);
        }
    },

    /** La liste de prix et la date du devis, qui chiffrent la configuration (D-537). */
    _orderPricing() {
        const order = this.props.record.model.root.data;
        return {
            pricelist_id: (order.pricelist_id && order.pricelist_id[0]) || false,
            date_order: order.date_order ? serializeDateTime(order.date_order) : false,
        };
    },

    /**
     * Les PRODUITS OPTIONNELS du produit configuré — D-537.
     *
     * ⓘ Chacun devient une ligne RATTACHÉE à celle du produit, comme les optionnels d'Odoo ;
     * un optionnel configurable ouvre sa propre fenêtre 3D avant de devenir la sienne.
     */
    _offerOptionalProducts(main, options) {
        this.dialog.add(OptionalProductsDialog, {
            products: options,
            withQuantity: true,
            add: (option, qty) => this._addLinkedLine(main, {
                product_id: [option.productId, option.name],
                product_uom_qty: qty || 1,
            }),
            configure: (option) => this._configureOptional(main, option),
        });
    },

    /** Ouvrir la fenêtre 3D d'un optionnel configurable ; vrai quand sa ligne est posée. */
    async _configureOptional(main, option) {
        const opened = await this.orm.call(
            "product.template", "web3d_open_configuration", [option.id],
            { session_id: false, ...this._orderPricing() },
        );
        return new Promise((resolve) => {
            // ⚠️ La fenêtre 3D se FERME avant que la ligne soit posée : sans ce drapeau, sa
            // fermeture répondrait « annulé » à une configuration validée (D-537).
            let confirmed = false;
            this.dialog.add(ConfiguratorDialog, {
                token: opened.token,
                initialState: opened.state,
                sessionId: opened.sessionId,
                productName: option.name,
                onConfirmed: async ({ productId, sessionId }) => {
                    if (!productId) return;
                    confirmed = true;
                    await this._addLinkedLine(main, {
                        product_id: [productId, option.name],
                        config_session_id: [sessionId, ""],
                    });
                    resolve(true);
                },
            }, { onClose: () => { if (!confirmed) resolve(false); } });
        });
    },

    /** Le lien d'une ligne vers celle du produit : `virtual_id` tant qu'elle est neuve. */
    async _linkTo(main) {
        if (!main.isNew) {
            return { linked_line_id: [main.resId, main.data.name || ""] };
        }
        let virtualId = main.data.virtual_id;
        if (!virtualId) {
            virtualId = uuid();
            await main.update({ virtual_id: virtualId });
        }
        return { linked_virtual_id: virtualId };
    },

    async _addLinkedLine(main, values) {
        const link = await this._linkTo(main);
        const record = await main.model.root.data.order_line.addNewRecord(
            { position: "bottom", mode: "readonly" });
        await record.update({ ...values, ...link });
        return true;
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
     * elles sont retirées puis reposées.
     * ⚠️ Sauf les lignes d'un PRODUIT OPTIONNEL (`optionTmplIds`) : rattachées elles aussi, elles
     * disparaîtraient à chaque correction de la configuration (D-537).
     *
     * ⚠️ **Côté client, et nulle part ailleurs** : `_web_after_confirm` (serveur) ne crée pas
     * ces lignes, sans quoi reconfigurer une ligne enregistrée les poserait deux fois.
     */
    async _applySeparateLines(main, separateLines, optionTmplIds = []) {
        const lines = main.model.root.data.order_line;
        for (const old of getLinkedSaleOrderLines(main)) {
            if (optionTmplIds.includes(old.data.product_template_id?.[0])) continue;
            await lines.delete(old);
        }
        for (const line of (separateLines || []).filter((line) => line.productId)) {
            await this._addLinkedLine(main, {
                product_id: [line.productId, line.name],
                product_uom_qty: line.qty || 1,
            });
        }
    },
});
