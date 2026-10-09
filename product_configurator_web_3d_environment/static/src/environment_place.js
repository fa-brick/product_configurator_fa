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
    },

    _load(state) {
        super._load(state);
        this.state.placements = state.placements || [];
    },

    /** La prochaine configuration à construire hors de l'écran pour la montrer, ou rien. */
    get placementToRender() {
        return (this.state.placements || []).find((placement) => placement.token
            && !this.state.shownTokens.includes(placement.token));
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
        this.state.selection = { kind: "opening", id: bay.id };
    },
});
