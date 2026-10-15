/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
/**
 * answer_list.js — Les RÉPONSES d'une question, dans la forme réglée sur son attribut (W-113, E-3c-1, D-451).
 *
 * Sorti de la page du configurateur pour qu'un autre hôte — la barre de droite de l'éditeur d'environnement —
 * montre une liste de matières « comme un attribut, et rien de plus ». Les formes : ligne résumé, carte, grande
 * pastille, couleur, liste déroulante, cases, radio et pastilles ; les dispositions : liste complète, rangée qui
 * défile, une rangée + « Voir tout » (D-382).
 *
 * Le composant ne RÉPOND pas : il dit ce qu'on a touché (`onPick`) et qu'on veut tout voir (`onOpenPanel`) ;
 * l'hôte décide. La saisie libre (D-353) reste à la page : elle n'est pas une forme.
 *
 * ⚠️ Pas de composant à emplacement pour la rangée qui défile : la rangée se règle ici par le DOM (L-453).
 */
import { Component, onMounted, onPatched, useRef } from "@odoo/owl";
import { layoutOn, lineOf, pickedAnswer, revealScrollLeft, rowEdges }
    from "@product_configurator_web_3d/configurator_state";

export class AnswerList extends Component {
    static template = "product_configurator_web_3d.AnswerList";
    static props = {
        // `{id, name, displayType, swatchMark, answerSize, answerLayout, categories, values}` (`toQuestion`).
        question: Object,
        onPick: Function,
        onOpenPanel: { type: Function, optional: true },
        // ⓘ En mode compact, une grille devient une rangée qui défile (D-389).
        compact: { type: Boolean, optional: true },
        // La largeur utile mesurée par l'hôte — la rangée `line` en tire son nombre de réponses.
        lineWidth: { type: Number, optional: true },
    };

    setup() {
        this.rowRef = useRef("row");
        onMounted(() => this._settleRow());
        onPatched(() => this._settleRow());
    }

    /** ⓘ Le nom que les gabarits Carte et Grande pastille lisent, comme dans la page. */
    get question() {
        return this.props.question;
    }

    pick(value) {
        this.props.onPick(value);
    }

    openPanel() {
        this.props.onOpenPanel?.();
    }

    onSelect(ev) {
        const chosenId = Number(ev.target.value);
        const value = this.question.values.find((v) => v.id === chosenId);
        if (value) this.pick(value);
    }

    /** La disposition À L'ÉCRAN : une grille devient une rangée en mode compact (D-389). */
    layoutOn(question) {
        return layoutOn(question, !!this.props.compact);
    }

    /**
     * Les réponses MONTRÉES : toutes, ou — en disposition `line` — celles d'une seule ligne et le compte de celles
     * qui restent (D-382).
     */
    shownAnswers(question) {
        if (this.layoutOn(question) !== "line") return { values: question.values, more: 0 };
        return lineOf(question.values, this.props.lineWidth || 0, question.displayType, question.answerSize);
    }

    pickedAnswer(question) {
        return pickedAnswer(question);
    }

    /**
     * Le nom d'une réponse suivi de son supplément — pour les formes sans place sous le libellé : l'infobulle d'une
     * couleur, l'option d'une liste déroulante (W-100).
     */
    answerTitle(value) {
        return value.extra ? `${value.name} (${value.extra})` : value.name;
    }

    /** Une question est répondue dès qu'une de ses valeurs est retenue. */
    isAnswered(question) {
        return question.values.some((value) => value.chosen);
    }

    /** Ce qui est choisi, en une clé — ce que la rangée compare à ce qu'elle a déjà montré (D-382). */
    chosenKey(question) {
        return question.values.filter((value) => value.chosen).map((value) => value.id).join(",");
    }

    /**
     * Régler la rangée qui défile après un rendu — D-382.
     *
     * ⚠️ Le choix n'est ramené que lorsqu'il CHANGE (`data-chosen` contre `data-shown`) : ramener la rangée à
     * chaque rendu reprendrait la main à qui la fait défiler.
     */
    _settleRow() {
        const row = this.rowRef.el;
        if (!row?.classList.contains("o_cfg3d_scrollrow--active")) return;
        const grid = row.firstElementChild;
        if (!grid) return;
        if (row.dataset.chosen !== row.dataset.shown) {
            row.dataset.shown = row.dataset.chosen;
            const chosen = grid.querySelector(".o_cfg3d_card--chosen, .o_cfg3d_bigswatch--chosen");
            if (chosen) {
                // ⓘ `offsetLeft` se lit depuis la grille, qui est positionnée (SCSS).
                const left = revealScrollLeft(grid.scrollLeft, grid.clientWidth, chosen.offsetLeft, chosen.offsetWidth);
                if (left !== null) grid.scrollLeft = left;
            }
        }
        this._markEdges(row);
    }

    /** Les bords atteints d'une rangée — ce qui cache la flèche devenue inutile. */
    _markEdges(row) {
        const grid = row.firstElementChild;
        const edges = rowEdges(grid.scrollLeft, grid.clientWidth, grid.scrollWidth);
        // ⓘ Des classes posées à la main : OWL ne retire que celles qu'il gère lui-même.
        row.classList.toggle("o_cfg3d_scrollrow--start", edges.start);
        row.classList.toggle("o_cfg3d_scrollrow--end", edges.end);
    }

    /** Le défilement d'une rangée, capturé sur elle — et le survol, qui la remesure. */
    onRowScroll(ev) {
        const row = ev.currentTarget;
        if (row.classList.contains("o_cfg3d_scrollrow--active") && row.firstElementChild) {
            this._markEdges(row);
        }
    }

    onRowArrow(ev, direction) {
        const grid = ev.currentTarget.closest(".o_cfg3d_scrollrow")?.firstElementChild;
        if (grid) grid.scrollBy({ left: direction * grid.clientWidth * 0.8, behavior: "smooth" });
    }

    get chooseLabel() { return _t("Choose…"); }
    get seeAllLabel() { return _t("See all"); }
}
