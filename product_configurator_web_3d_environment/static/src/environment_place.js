/** @odoo-module */
/**
 * environment_place.js — POSER un produit dans une baie de l'environnement (W-111, étape 8.4c).
 *
 * Remplit `placeProduct`, laissé vide par l'éditeur d'environnement (LGPL) : la pose crée une
 * configuration, et la configuration est l'affaire du configurateur (AGPL) — ce pont les joint.
 */
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { EnvironmentEditor } from "@product_editor_environment/editor/environment_editor";

patch(EnvironmentEditor.prototype, {
    setup() {
        super.setup();
        this.state.placements = [];
    },

    _load(state) {
        super._load(state);
        this.state.placements = state.placements || [];
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
