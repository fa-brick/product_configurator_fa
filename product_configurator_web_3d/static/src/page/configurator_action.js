/** @odoo-module **/
/**
 * Le configurateur 3D en DIALOGUE, au back-office — D-262.
 *
 * ⚠️ **Une action `act_url` ouvre un ONGLET**, et un onglet fait perdre de vue ce
 * qu'on était en train de faire : le devis, la fiche produit. Gerry l'a relevé le
 * 2026-09-07 : *« une nouvelle page s'ouvre au lieu d'un dialogue comme pour une
 * ligne de devis »*.
 *
 * ⓘ **Une action CLIENTE en `target: "new"`** : Odoo l'enveloppe lui-même dans un
 * dialogue, sans qu'on ait à en écrire un. Ce composant ne dessine donc rien —
 * il monte `ConfiguratorPage`, le composant de la page publique, et lui passe ce
 * que le serveur a déjà mis dans l'action.
 *
 * ⚠️ **L'état voyage AVEC l'action.** Le serveur l'a calculé pour construire son
 * URL ; le redemander au montage coûterait un aller-retour pour la même réponse,
 * et la page attendrait devant un écran vide (D-249).
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ConfiguratorPage } from "./configurator_page";

export class ConfiguratorAction extends Component {
    static template = "product_configurator_web_3d.ConfiguratorAction";
    static components = { ConfiguratorPage };
    static props = ["*"];

    get token() {
        return this.props.action?.params?.token || "";
    }

    get initialState() {
        return this.props.action?.params?.state || undefined;
    }

    /**
     * ⓘ Terminer FERME le dialogue : on revient là d'où l'on vient — la fiche
     * produit ou le devis —, ce qu'un onglet ne permettait pas.
     */
    onConfirmed() {
        this.props.close?.();
    }
}

registry.category("actions").add(
    "product_configurator_web_3d.configurator", ConfiguratorAction);
