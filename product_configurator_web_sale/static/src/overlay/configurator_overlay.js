/** @odoo-module */
/**
 * configurator_overlay.js — Le configurateur PRÉPARÉ pendant qu'on lit la fiche.
 *
 * ⚠️ **Le clic ne peut être instantané que si l'on NE NAVIGUE PAS.** Mesuré le
 * 2026-09-06 : le bundle du moteur est déjà en cache sur la fiche produit (c'est le
 * même fichier, 2 965 Kio), l'état ne coûte que 93 ms — mais la CONSTRUCTION de la
 * scène coûte une à deux secondes de calcul, et **aucun calcul ne survit à un
 * changement de page**. Préparer d'avance n'a donc de sens qu'en restant sur place.
 *
 * ─ Ce que ce composant fait ─────────────────────────────────────────────────
 *
 * ⓵ Dès que la fiche est affichée, il demande une configuration (`/configurator/prepare`)
 *    et monte la page du configurateur, **invisible**, qui construit sa scène.
 * ⓶ Au clic sur « Configurer », il la découvre — il n'y a plus rien à attendre.
 * ⓷ Et il pousse l'URL `/configurator/<jeton>` dans l'historique : la page reste
 *    PARTAGEABLE et REPRENABLE (arbitrage Gerry, 2026-09-06). Le retour arrière la
 *    referme.
 *
 * ⚠️ **Le lien reste un vrai lien.** S'il est cliqué avant que la préparation
 * n'aboutisse — ou si le JavaScript échoue —, il navigue comme avant. La promesse se
 * dégrade, elle ne casse pas.
 */
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";

/** Le bouton que ce composant détourne, s'il le trouve. */
const TRIGGER = ".o_cfg3d_configure";

export class ConfiguratorOverlay extends Component {
    static template = "product_configurator_web_sale.ConfiguratorOverlay";
    static components = { ConfiguratorPage };
    static props = {
        productTmplId: { type: Number },
    };

    setup() {
        this.state = useState({ token: null, initialState: null, open: false });
        onMounted(() => {
            this._bindTrigger();
            this._prepareWhenIdle();
            browser.addEventListener("popstate", this._onPopState);
        });
        onWillUnmount(() => {
            // ⚠️ TOUJOURS déverrouiller en partant : un composant démonté qui laisse le
            // corps figé condamnerait la page à ne plus défiler, sans rien à l'écran
            // pour l'expliquer.
            this._lockPage(false);
            browser.removeEventListener("popstate", this._onPopState);
            this._trigger?.removeEventListener("click", this._onTriggerClick);
        });
    }

    /**
     * Préparer QUAND LA FICHE EST AFFICHÉE, et pas avant (arbitrage Gerry).
     *
     * ⚠️ `requestIdleCallback` et non un `setTimeout` : la préparation ne doit pas
     * disputer le fil à ce que le visiteur est en train de lire — images, prix,
     * description. Elle prend ce qui reste, et Safari n'en a pas, d'où le repli.
     */
    _prepareWhenIdle() {
        const start = () => this._prepare();
        if (browser.requestIdleCallback) {
            browser.requestIdleCallback(start, { timeout: 3000 });
        } else {
            browser.setTimeout(start, 1200);
        }
    }

    async _prepare() {
        try {
            const answer = await rpc("/configurator/prepare",
                                     { product_tmpl_id: this.props.productTmplId });
            if (!answer || answer.error) return;
            // ⓘ Poser les deux ENSEMBLE : la page se monte sur le jeton, et son
            // état préparé lui évite un second aller-retour.
            this.state.token = answer.token;
            this.state.initialState = answer.state;
        } catch (e) {
            // ⚠️ MUET ET SANS CONSÉQUENCE : le lien navigue toujours. Une préparation
            // qui échoue ne doit rien coûter à qui clique.
            console.warn("[configurateur] préparation impossible :", e);
        }
    }

    _bindTrigger() {
        this._trigger = document.querySelector(TRIGGER);
        this._trigger?.addEventListener("click", this._onTriggerClick);
    }

    /**
     * ⚠️ On ne prend la main QUE si la scène est prête. Sinon on laisse le lien
     * faire ce qu'il a toujours fait — mieux vaut la navigation d'avant qu'un
     * bouton qui ne répond pas.
     */
    _onTriggerClick = (ev) => {
        if (!this.state.token) return;
        ev.preventDefault();
        this.open();
    };

    /**
     * Verrouiller la page DESSOUS pendant que le configurateur est ouvert.
     *
     * ⚠️ **Un recouvrement qui masque à l'œil ne masque pas à la molette.** La fiche
     * produit continuait de défiler derrière, et sa barre restait visible à droite
     * (constat de Gerry, 2026-09-06). `position: fixed` couvre la vue ; il ne retire
     * pas le document du chemin des événements de défilement.
     *
     * ⓘ Une CLASSE sur le corps plutôt qu'un style écrit à la main : elle se retire
     * d'un seul geste, et la feuille de style reste le seul endroit qui décide.
     */
    _lockPage(locked) {
        document.body.classList.toggle("o_cfg3d_locked", !!locked);
    }

    open() {
        this.state.open = true;
        this._lockPage(true);
        // L'URL du configurateur, poussée dans l'historique : partageable et
        // reprenable, exactement comme si l'on y avait navigué.
        browser.history.pushState({ configurator: this.state.token }, "",
                                  `/configurator/${this.state.token}`);
    }

    /**
     * Fermer, c'est REVENIR EN ARRIÈRE — jamais poser un état de plus.
     *
     * ⓘ L'historique est déjà la source de vérité (on y a poussé l'URL du
     * configurateur) : fermer autrement laisserait l'adresse mentir sur ce que
     * l'écran montre.
     */
    close() {
        browser.history.back();
    }

    /** Le retour arrière referme, et rend son URL à la fiche. */
    _onPopState = () => {
        this.state.open = false;
        this._lockPage(false);
    };
}

registry.category("public_components")
    .add("product_configurator_web_sale.ConfiguratorOverlay", ConfiguratorOverlay);
