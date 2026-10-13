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
 * Étape 8.4e : CONFIGURER dans l'environnement. La même page, en panneau seul, est la barre de DROITE d'un
 * produit posé sélectionné (W-113, E-3b) ; chaque réponse reconstruit le produit, dont la copie remplace celle
 * de la baie. La flèche ramène à l'environnement sans rien valider : la configuration reste en cours (Q-11.4).
 * Le produit SUIT sa baie quand elle change, en gardant l'écart que le client y a mis (D-424) : le
 * serveur le fait à l'enregistrement, ce pont redessine ce qui a suivi.
 */
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { EnvironmentEditor } from "@product_editor_environment/editor/environment_editor";
import { ConfiguratorPage } from "@product_configurator_web_3d/page/configurator_page";
import { disposeSnapshot } from "@product_editor/engine/three/scene_snapshot";
import { holeContourKey } from "@product_editor_environment/engine/product_hole";

EnvironmentEditor.components = { ...EnvironmentEditor.components, ConfiguratorPage };

patch(EnvironmentEditor.prototype, {
    setup() {
        super.setup();
        this.state.placements = [];
        // ⓘ Les configurations déjà montrées dans leur baie : `jeton|contour du trou` (E-3d-4c) — un trou qui change
        // de forme redessine son produit, même à cotes égales.
        this.state.shownTokens = [];
        // ⓘ Relance la page de la barre de droite quand sa configuration a changé sans elle.
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
            this.state.shownTokens = this.state.shownTokens.filter((key) => !followed.includes(key.split("|")[0]));
            if (followed.includes(this.configuringPlacement?.token)) this.state.configureSerial++;
        }
        if (result.messages?.length) this.state.messages = result.messages;
        this._reloadPlacements();
    },

    /** Le produit posé dans un trou — sa carte est cochée dans la liste de Permuter. */
    placedProductId(openingId) {
        return this.placementOf(openingId)?.productId || null;
    },

    /** Le produit posé dans une baie, sous elle dans l'arbre de la barre latérale (W-113, E-2b). */
    placedProductName(openingId) {
        return this.placementOf(openingId)?.productName || null;
    },

    /** Un produit posé fige aussi la forme : la changer effacerait sa baie (Q-14.4). */
    get canChangeShape() {
        return super.canChangeShape && !(this.state.placements || []).length;
    },

    /**
     * Le placement en cours de configuration : celui de la baie SÉLECTIONNÉE (W-113, E-3b) — seulement là où l'on
     * peut poser.
     */
    get configuringPlacement() {
        const opening = this.selectedOpening;
        if (!this.state.canPlace || this.readonly || !opening) return null;
        // ⓘ Permuter (Q-26.2) : la barre de droite liste les produits qui peuvent le remplacer, pas sa configuration.
        if (this.state.swapOpeningId === opening.id) return null;
        const placement = this.placementOf(opening.id);
        return placement?.token ? placement : null;
    },

    /** La page du configurateur EST la barre de droite d'un produit posé : elle a son titre et sa flèche. */
    get rightReplaced() {
        return super.rightReplaced || !!this.configuringPlacement;
    },

    configure(openingId) {
        this.state.selection = { kind: "opening", id: openingId };
        this.state.faceMenu = null;
    },

    /** Fermer la barre de droite d'un produit : ses écarts à la baie ont pu changer, on les relit. */
    closeRight() {
        const configuring = this.configuringPlacement;
        super.closeRight();
        if (configuring) this._reloadPlacements();
    },

    /** La flèche de la page : retour à l'environnement, la configuration reste en cours (Q-11.4). */
    stopConfiguring() {
        this.closeRight();
    },

    /** Le menu flottant gagne le RETRAIT du produit (étape 8.4f). */
    bayMenuActions(opening) {
        const actions = super.bayMenuActions(opening);
        if (this.placementOf(opening.id)) {
            actions.push({ id: "remove", label: _t("Remove"), icon: "delete-outline", danger: true });
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
        if (this.selectedOpening?.id === openingId) this.selectRoot();
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
            && placement !== configuring
            && !this.state.shownTokens.includes(this._shownKey(placement.openingId, placement.token)));
    },

    /**
     * La copie du produit construit arrive : elle se pose dans sa baie.
     * ⚠️ Une copie dont la baie a changé de produit entre-temps est libérée, jamais montrée.
     */
    onPlacedScene(openingId, token, group, info = null) {
        const key = this._shownKey(openingId, token);
        if (!this.state.shownTokens.includes(key)) this.state.shownTokens.push(key);
        if (this.placementOf(openingId)?.token !== token) {
            disposeSnapshot(group);
            return;
        }
        // ⓘ Avec son perçage : le produit se cale par lui sur son trou (E-3d-4c).
        this.setBayObject(openingId, group, info);
    },

    /** Ce qui dit qu'un produit est montré pour son trou tel qu'il est : son jeton et le contour du trou. */
    _shownKey(openingId, token) {
        return `${token}|${holeContourKey(this.holeContourOf(openingId))}`;
    },

    /** La clé du contour d'un trou, pour la page de configuration de la barre de droite (recréée s'il change). */
    holeContourKeyOf(openingId) {
        return holeContourKey(this.holeContourOf(openingId));
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
