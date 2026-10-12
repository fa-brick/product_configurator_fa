/** @odoo-module */
/**
 * environment_materials.js — Les listes de matières de la barre de droite, dans l'AFFICHAGE d'un attribut
 * (W-113, E-3c-3, D-451).
 *
 * L'éditeur d'environnement (LGPL) range ses matières par usage en QUESTIONS (`rightSections`) et les montre en
 * pastilles simples ; ce pont les montre par les composants de la page du configurateur — la même forme, la même
 * marque, la même taille, la même disposition qu'un attribut, et rien de plus (§21.5) —, et règle cet affichage
 * dans l'onglet Infos.
 */
import { onMounted, onPatched } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { EnvironmentEditor } from "@product_editor_environment/editor/environment_editor";
import { AnswerList } from "@product_configurator_web_3d/answers/answer_list";
import { AnswerPanel } from "@product_configurator_web_3d/answers/answer_panel";
import { answerLayoutOf } from "@product_configurator_web_3d/configurator_state";

EnvironmentEditor.components = { ...EnvironmentEditor.components, AnswerList, AnswerPanel };

patch(EnvironmentEditor.prototype, {
    setup() {
        super.setup();
        // ⓘ Le panneau de choix d'une liste (« Voir tout », ligne résumé) : `{use, key}`, ou rien.
        this.state.materialPanel = null;
        // ⓘ La largeur utile de la barre de droite, mesurée : la rangée « une ligne + Voir tout » en tire son compte.
        this.state.rightLineWidth = 0;
        this.state.materialDisplayOptions = null;
        onMounted(() => this._measureRightBody());
        onPatched(() => this._measureRightBody());
    },

    _load(state) {
        super._load(state);
        this.state.materialDisplayOptions = state.materialDisplayOptions || null;
        this.state.materialPanel = null;
    },

    /** Une liste de matières, avec l'affichage de son usage — ⓘ sans lui (un serveur pas à jour), des pastilles. */
    _materialSection(use, chosenId) {
        const section = super._materialSection(use, chosenId);
        const row = this.state.materialUses.find((u) => u.use === use);
        if (!row?.displayType) return section;
        const question = { ...section, displayType: row.displayType, swatchMark: row.swatchMark,
                           answerSize: row.answerSize, answerLayout: row.answerLayout };
        question.answerLayout = answerLayoutOf(question);
        return question;
    },

    /** La liste dont le panneau de choix est ouvert — relue à chaque rendu ; `null` si elle n'est plus montrée. */
    get materialPanelQuestion() {
        const panel = this.state.materialPanel;
        return panel ? this.rightSections.find((section) => section.id === panel.use) || null : null;
    },

    openMaterialPanel(use) {
        // ⓘ Une clé neuve à chaque ouverture : le panneau repart de zéro (recherche, vue, catégorie).
        this._materialPanelKey = (this._materialPanelKey || 0) + 1;
        this.state.materialPanel = { use, key: this._materialPanelKey };
    },

    closeMaterialPanel() {
        this.state.materialPanel = null;
    },

    /** Changer d'élément ferme le panneau de choix : il appartenait à la liste d'avant. */
    selectRoot() {
        super.selectRoot();
        this.state.materialPanel = null;
    },

    /** ⓘ N'écrit que ce qui change : une écriture relance un rendu, donc ce même crochet. */
    _measureRightBody() {
        const body = this.rootRef.el?.querySelector(".o_env_right_body");
        if (!body) return;
        const style = window.getComputedStyle(body);
        const width = Math.floor(body.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight));
        if (width > 0 && width !== this.state.rightLineWidth) this.state.rightLineWidth = width;
    },

    // ── L'affichage d'un usage, dans l'onglet Infos (Q-24.2) ────────────────

    /** Les réglages d'un usage : la marque seulement pour une grande pastille, où elle a un effet. */
    materialDisplayFields(use) {
        const fields = [
            { key: "displayType", label: _t("Display type") },
            { key: "swatchMark", label: _t("Selection mark") },
            { key: "answerSize", label: _t("Answer size") },
            { key: "answerLayout", label: _t("Answer layout") },
        ];
        return use.displayType === "swatch" ? fields : fields.filter((field) => field.key !== "swatchMark");
    },

    displayOptions(key) {
        return this.state.materialDisplayOptions?.[key] || [];
    },

    /** ⓘ La disposition RÉGLÉE, pas l'effective : une disposition sans effet sur cette forme reste choisie. */
    useDisplayValue(use, key) {
        return key === "answerLayout" ? use.answerLayoutSet || use.answerLayout : use[key];
    },

    onMaterialDisplay(use, key, ev) {
        this.saveMaterialUse(use, { [key]: ev.target.value });
    },
});
