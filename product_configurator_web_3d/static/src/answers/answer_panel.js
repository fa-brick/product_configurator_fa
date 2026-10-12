/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
/**
 * answer_panel.js — Le PANNEAU DE CHOIX d'une question : toutes ses réponses, une recherche, une vue, les pastilles
 * de catégories (D-382). Sorti de la page du configurateur avec la liste des réponses (W-113, E-3c-1, D-451).
 *
 * Il reste ouvert jusqu'à sa flèche, choix simple compris : ce qu'on choisit se voit dans la 3D, à côté. L'hôte
 * le ferme (`onClose`) et répond (`onPick`) ; la recherche, la vue et la catégorie vivent ici, et repartent de
 * zéro à chaque ouverture.
 */
import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { filterAnswers, filterByCategory, isImageForm, panelChips, panelViewOf }
    from "@product_configurator_web_3d/configurator_state";

export class AnswerPanel extends Component {
    static template = "product_configurator_web_3d.AnswerPanel";
    static props = {
        question: Object,
        onPick: Function,
        onClose: Function,
        // ⓘ Sur téléphone, une poignée ferme aussi le panneau (D-389).
        compact: { type: Boolean, optional: true },
        // ⚠️ La raison d'un refus (D-178) s'affiche DANS le panneau : celle de la colonne est dessous.
        reason: { type: [String, { value: null }], optional: true },
    };

    setup() {
        this.state = useState({ search: "", view: panelViewOf(this.props.question), category: null });
        this.panelSearchRef = useRef("panelSearch");
        onMounted(() => {
            // ⚠️ Pas au doigt : le clavier du téléphone mangerait la moitié du panneau.
            // ⚠️ `preventScroll` : le panneau glisse encore, et montrer la recherche faisait défiler la page entière.
            if (this.panelSearchRef.el && window.matchMedia("(hover: hover)").matches) {
                this.panelSearchRef.el.focus({ preventScroll: true });
            }
        });
    }

    /** ⓘ Le nom que les gabarits Carte et Grande pastille lisent, comme dans la page. */
    get question() {
        return this.props.question;
    }

    pick(value) {
        this.props.onPick(value);
    }

    isImageForm(question) {
        return isImageForm(question);
    }

    /** Les réponses du panneau, filtrées par la pastille de catégorie PUIS par la recherche. */
    panelValues(question) {
        return filterAnswers(filterByCategory(question.values, this.state.category), this.state.search);
    }

    /** Les pastilles de catégories — aucune sous deux groupes (D-382). */
    panelChips(question) {
        return panelChips(question, this.allLabel, this.otherLabel);
    }

    onPanelCategory(key) {
        this.state.category = key;
    }

    onPanelSearch(ev) {
        this.state.search = ev.target.value;
    }

    onPanelView(view) {
        this.state.view = view;
    }

    get backLabel() { return _t("Back"); }
    get closeLabel() { return _t("Close"); }
    get searchLabel() { return _t("Search…"); }
    get noMatchLabel() { return _t("No answer matches this search."); }
    get listViewLabel() { return _t("List"); }
    get smallViewLabel() { return _t("Small grid"); }
    get largeViewLabel() { return _t("Large grid"); }
    get allLabel() { return _t("All"); }
    get otherLabel() { return _t("Others"); }
}
