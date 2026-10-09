/** @odoo-module */
/**
 * environment_place.js — POSER un produit dans une baie de l'environnement (W-111, étape 8.4c).
 *
 * Remplit `placeProduct`, laissé vide par l'éditeur d'environnement (LGPL) : la pose crée une
 * configuration, et la configuration est l'affaire du configurateur (AGPL) — ce pont les joint.
 *
 * Étape 8.4d : le produit posé se MONTRE dans sa baie. La page du configurateur, montée hors de
 * l'écran, construit la configuration avec son viewer et en rend une copie habillée (`onScene`),
 * que l'éditeur pose dans la baie. Une page à la fois : chaque viewer est un contexte WebGL.
 *
 * Étape 8.4e : CONFIGURER dans l'environnement. La même page, en panneau seul, prend la barre
 * latérale ; chaque réponse reconstruit le produit, dont la copie remplace celle de la baie. La
 * flèche ramène à l'environnement sans rien valider : la configuration reste en cours (Q-11.4).
 * Le produit SUIT sa baie quand elle change, en gardant l'écart que le client y a mis (D-424) : le
 * serveur le fait à l'enregistrement, ce pont redessine ce qui a suivi.
 */
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { EnvironmentEditor } from "@product_editor_environment/editor/environment_editor";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";
import { disposeSnapshot } from "@product_editor/engine/three/scene_snapshot";

EnvironmentEditor.components = { ...EnvironmentEditor.components, ConfiguratorPage };

patch(EnvironmentEditor.prototype, {
    setup() {
        super.setup();
        this.state.placements = [];
        // ⓘ Les configurations déjà montrées dans leur baie, par jeton de session.
        this.state.shownTokens = [];
        // ⓘ La baie dont on configure le produit dans la barre latérale, ou rien.
        this.state.configuringId = null;
        // ⓘ Relance la page de la barre latérale quand sa configuration a changé sans elle.
        this.state.configureSerial = 0;
    },

    /** Relire les placements — leur écart à la baie a pu changer. */
    async _reloadPlacements() {
        const state = await rpc("/environment/state", { token: this.props.token });
        if (!state.error) this.state.placements = state.placements || [];
    },

    /** Les produits qui ont suivi leur baie se redessinent ; un refus se dit (D-424). */
    onSaved(result) {
        super.onSaved(result);
        const followed = result.followed || [];
        if (followed.length) {
            this.state.shownTokens = this.state.shownTokens.filter((token) => !followed.includes(token));
            if (followed.includes(this.configuringPlacement?.token)) this.state.configureSerial++;
        }
        if (result.messages?.length) this.state.messages = result.messages;
        this._reloadPlacements();
    },

    /** Le placement en cours de configuration — seulement là où l'on peut poser. */
    get configuringPlacement() {
        if (!this.state.canPlace || this.readonly || !this.state.configuringId) return null;
        const placement = this.placementOf(this.state.configuringId);
        return placement?.token ? placement : null;
    },

    configure(openingId) {
        this.state.selection = { kind: "opening", id: openingId };
        this.state.configuringId = openingId;
    },

    /** La flèche : retour à l'environnement, la configuration reste en cours (Q-11.4). */
    stopConfiguring() {
        this.state.configuringId = null;
        this.state.selection = null;
        this._reloadPlacements();
    },

    /** Le menu flottant gagne le RETRAIT du produit (étape 8.4f). */
    bayMenuActions(opening) {
        const actions = super.bayMenuActions(opening);
        if (this.placementOf(opening.id)) {
            actions.push({ id: "remove", label: _t("Remove"), icon: "fa-trash", danger: true });
        }
        return actions;
    },

    async onBayMenu(actionId, openingId) {
        if (actionId !== "remove") return super.onBayMenu(actionId, openingId);
        const result = await rpc("/environment/unplace", { token: this.props.token, opening_id: openingId });
        if (result.error) {
            this.state.messages = [_t("This product could not be removed.")];
            return;
        }
        if (this.state.configuringId === openingId) this.state.configuringId = null;
        this.state.placements = this.state.placements.filter((placement) => placement.openingId !== openingId);
        this.setBayObject(openingId, null);
    },

    /** L'écart d'une mesure à la baie, lisible : « baie − 400 mm », ou rien s'il est nul. */
    offsetLabel(placement, key) {
        const offset = placement.offsets?.[key];
        if (!offset) return "";
        const fmt = new Intl.NumberFormat(document.documentElement.lang || undefined, { maximumFractionDigits: 1 });
        return offset > 0 ? _t("bay + %(offset)s mm", { offset: fmt.format(offset) })
            : _t("bay − %(offset)s mm", { offset: fmt.format(-offset) });
    },

    onPickBayObject(openingId) {
        if (this.placementOf(openingId)?.token && this.state.canPlace && !this.readonly) {
            this.configure(openingId);
        } else {
            super.onPickBayObject(openingId);
        }
    },

    _load(state) {
        super._load(state);
        this.state.placements = state.placements || [];
    },

    /** La prochaine configuration à construire hors de l'écran pour la montrer, ou rien. */
    get placementToRender() {
        // ⓘ Celui qu'on configure a sa page dans la barre latérale : elle fait sa copie elle-même.
        const configuring = this.configuringPlacement;
        return (this.state.placements || []).find((placement) => placement.token
            && placement !== configuring && !this.state.shownTokens.includes(placement.token));
    },

    /**
     * La copie du produit construit arrive : elle se pose dans sa baie.
     * ⚠️ Une copie dont la baie a changé de produit entre-temps est libérée, jamais montrée.
     */
    onPlacedScene(openingId, token, group) {
        if (!this.state.shownTokens.includes(token)) this.state.shownTokens.push(token);
        if (this.placementOf(openingId)?.token !== token) {
            disposeSnapshot(group);
            return;
        }
        this.setBayObject(openingId, group);
    },

    /** Le produit posé dans une baie, ou rien. */
    placementOf(openingId) {
        return (this.state.placements || []).find((placement) => placement.openingId === openingId);
    },

    async placeProduct(bay, product) {
        const result = await rpc("/environment/place", {
            token: this.props.token, opening_id: bay.id, product_tmpl_id: product.id,
        });
        if (result.error) {
            this.state.messages = [result.message || _t("This product cannot be placed in this bay.")];
            return;
        }
        this.state.messages = [];
        this.state.placements = [
            ...this.state.placements.filter((placement) => placement.openingId !== bay.id), result.placement,
        ];
        // ⓘ Le produit posé est sélectionné pour commencer sa configuration (parcours §10).
        if (result.placement.token) this.configure(bay.id);
        else this.state.selection = { kind: "opening", id: bay.id };
    },
});
