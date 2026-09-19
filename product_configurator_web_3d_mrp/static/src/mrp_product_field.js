/** @odoo-module **/
/**
 * Choisir un produit CONFIGURABLE sur un ordre de fabrication ouvre notre configurateur.
 *
 * Arbitrage de Gerry, 2026-09-19 : *« lorsque l'on clique sur nouveau et que l'on
 * sélectionne un produit configuré, que cela déclenche le configurateur comme lors d'un
 * devis — cela évite la présence inutile de ce bouton. »*
 *
 * ─ LE FAIT qui commande tout le reste ───────────────────────────────────────
 *
 * ⚠️ **Un produit configurable n'a AUCUNE variante tant qu'il n'a pas été configuré.**
 * Ce n'est pas un accident : `product_configurator_fa` surcharge `_create_variant_ids`
 * pour les en priver — *« these serve only as a template for the product configurator »*.
 *
 * Or le champ d'un ordre de fabrication est `product_id`, une VARIANTE. Un produit
 * configurable neuf est donc **absent de sa liste déroulante**, et il n'y a rien à
 * sélectionner — précisément pour les produits que ce lot doit servir. C'est la même
 * raison qui fait qu'une ligne de devis porte le MODÈLE et non la variante.
 *
 * ─ La réponse retenue (arbitrage Gerry) ─────────────────────────────────────
 *
 * ⓘ **Un seul champ à l'écran**, celui d'Odoo, dont la liste déroulante propose EN PLUS
 * les modèles configurables. En choisir un n'écrit rien : cela ouvre le configurateur, et
 * c'est lui qui produit la variante à poser. L'écran de fabrication ne change donc pas
 * d'aspect pour qui n'a pas de produits configurables.
 *
 * ⓘ **Et cela sert aussi à ROUVRIR.** Un ordre déjà configuré porte sa session ; rechoisir
 * le même modèle la reprend telle quelle au lieu d'ouvrir une page neuve. Un seul chemin,
 * celui qu'on emprunte déjà — ce qui rend inutile le bouton « Reconfigure » supprimé ici.
 */
import { registry } from "@web/core/registry";
import { Many2OneField, many2OneField } from "@web/views/fields/many2one/many2one_field";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { ConfiguratorDialog } from "@product_configurator_web_3d/configurator_dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/** Combien de modèles configurables la liste propose au plus. */
const CONFIGURABLE_LIMIT = 8;

/**
 * La liste déroulante du produit, augmentée des modèles CONFIGURABLES.
 *
 * ⓘ `loadOptionsSource` rend des options dont certaines portent une `action` au lieu
 * d'une valeur — c'est ainsi qu'Odoo ajoute « Créer… » et « Chercher plus… ». On s'y range,
 * plutôt que d'inventer un second champ ou un bouton.
 */
export class MrpConfigAutocomplete extends Many2XAutocomplete {
    static props = {
        ...Many2XAutocomplete.props,
        onConfigurableTemplate: { type: Function },
    };

    async loadOptionsSource(request) {
        const options = await super.loadOptionsSource(request);
        let modeles = [];
        try {
            modeles = await this.orm.call("product.template", "name_search", [], {
                name: request || "",
                args: [["config_ok", "=", true]],
                limit: CONFIGURABLE_LIMIT,
            });
        } catch {
            // ⓘ Une liste qui ne se charge pas ne doit pas emporter celle d'Odoo : on
            // rend ce qu'on a. Le pire cas est de ne pas proposer les configurables, pas
            // de casser le champ produit de tous les ordres de fabrication.
            return options;
        }
        // ⚠️ EN TÊTE, et avant « Chercher plus… » : ce sont des produits à part entière du
        // point de vue de l'utilisateur, pas une commande annexe.
        const extra = modeles.map(([id, name]) => ({
            label: _t("%s — configure", name),
            classList: "o_m2o_dropdown_option",
            action: () => this.props.onConfigurableTemplate(id, name),
        }));
        return [...extra, ...options];
    }
}

export class MrpConfigProductField extends Many2OneField {
    static components = {
        ...Many2OneField.components,
        Many2XAutocomplete: MrpConfigAutocomplete,
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialog = useService("dialog");
    }

    get Many2XAutocompleteProps() {
        return {
            ...super.Many2XAutocompleteProps,
            onConfigurableTemplate: (id, name) => this.openConfigurator(id, name),
        };
    }

    /**
     * Monter le MÊME dialogue que le devis, sur la MÊME préparation serveur.
     *
     * ⓘ `web3d_open_configuration` rend un jeton et l'état complet de la page — le pendant
     * back-office de `/configurator/prepare`. Une seule préparation pour les deux écrans :
     * ce qu'on change pour le client se voit ici le jour même ([[L-073]]).
     */
    async openConfigurator(templateId, templateName) {
        const session = this.props.record.data.config_session_id;
        const opened = await this.orm.call(
            "product.template", "web3d_open_configuration", [templateId],
            // ⓘ On REPREND la configuration de l'ordre quand il en a une.
            { session_id: (session && session[0]) || false },
        );
        this.dialog.add(ConfiguratorDialog, {
            token: opened.token,
            initialState: opened.state,
            sessionId: opened.sessionId,
            productName: templateName,
            onConfirmed: (result) => this.applyConfiguration(result, templateName),
        });
    }

    /**
     * Poser sur l'ordre ce que la configuration a produit.
     *
     * ⓘ Écrire `product_id` et `config_session_id` SUFFIT : Odoo recalcule la nomenclature
     * depuis le produit, comme pour n'importe quel changement de variante. C'est exactement
     * ce que fait la ligne de devis, aux deux champs près.
     */
    async applyConfiguration({ productId, sessionId }, templateName) {
        if (!productId) return;
        await this.props.record.update({
            product_id: [productId, templateName],
            config_session_id: [sessionId, ""],
        });
    }
}

export const mrpConfigProductField = {
    ...many2OneField,
    component: MrpConfigProductField,
    // ⚠️ `config_session_id` doit être CHARGÉ avec la fiche : sans cette ligne, rouvrir
    // une configuration existante partirait d'une page neuve — et la session déjà liée à
    // l'ordre serait silencieusement remplacée par une autre.
    fieldDependencies: [
        { name: "config_session_id", type: "many2one", relation: "product.config.session" },
    ],
};

registry.category("fields").add("mrp_config_product", mrpConfigProductField);
