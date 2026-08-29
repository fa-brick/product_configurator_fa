/**
 * L'ARBRE DU CONFIGURATEUR — la maquette de Gerry (D-210).
 *
 * Trois natures de lignes dans une seule liste : l'ÉTAPE en bandeau, l'ATTRIBUT,
 * et ses VALEURS indentées portant chacune leur condition.
 *
 * ⚠️ **Pourquoi un composant et pas une liste Odoo.** Une liste ne sait ni
 * s'imbriquer ni mêler deux modèles — or l'arbre en tient trois. Le serveur rend
 * donc UNE structure (`get_configurator_tree`), et ce composant l'affiche.
 *
 * ⚠️ **L'étape est un bandeau RENDU, pas un enregistrement de plus.** Le modèle
 * n'a pas changé (D-202) : elle reste un marqueur porté par la ligne qui l'ouvre.
 * C'est ce que la forme (A) promettait — *« le bandeau pourra venir plus tard
 * sans toucher au modèle »*.
 */
import {Component, onWillStart, onWillUpdateProps, useRef, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useService} from "@web/core/utils/hooks";
import {useSortable} from "@web/core/utils/sortable_owl";

/**
 * L'ordre des lignes d'attribut après un déplacement.
 *
 * ⚠️ **Seul un ATTRIBUT se déplace.** Un bandeau d'étape n'est pas un
 * enregistrement (D-202) et une valeur appartient à son attribut : les glisser
 * n'aurait rien à écrire. La fonction ne connaît donc que des identifiants de
 * lignes, et rend l'ordre à enregistrer.
 *
 * ⓘ Fonction PURE — c'est la seule part du glisser-déposer qui décide quelque
 * chose, donc la seule qui vaille d'être éprouvée hors du navigateur.
 */
export function reorder(lineIds, fromIndex, toIndex) {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) {
        return [...lineIds];
    }
    const next = [...lineIds];
    const [moved] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    return next;
}

/**
 * Où atterrit la ligne déposée, d'après la ligne restée AU-DESSUS d'elle.
 *
 * ⚠️ Le cœur ne dit pas un index, il dit un VOISIN (`previous`) : c'est la seule
 * chose qu'il sache après avoir promené un fantôme dans le DOM. Le décalage de
 * un vient de ce que la ligne emportée occupe encore sa place dans `ids` —
 * descendre après le voisin n° 3 mène au rang 3, pas 4, si l'on venait d'avant.
 *
 * ⓘ `previousId === null` veut dire « déposé en tête ». Un voisin INCONNU rend
 * −1 : `reorder` traite un index négatif comme un refus, et rien ne bouge.
 *
 * ⓘ Fonction PURE, partagée par les deux ordres — celui des attributs et celui
 * des valeurs.
 */
export function dropIndex(ids, fromIndex, previousId) {
    if (previousId === null) {
        return 0;
    }
    const at = ids.indexOf(previousId);
    if (at < 0) {
        return -1;
    }
    return fromIndex < at ? at : at + 1;
}

/**
 * Met l'arbre à plat, dans l'ordre où il s'affiche.
 *
 * ⚠️ Une valeur ne s'affiche QUE si son attribut est déplié. Rendre toutes les
 * valeurs et les cacher en CSS ferait payer un produit à trois cents valeurs
 * pour rien — et c'est justement le cas que le dialogue existe pour éviter.
 *
 * ⓘ Fonction PURE, exportée : c'est la seule part de ce composant qui décide
 * quelque chose, donc la seule qui vaille d'être éprouvée hors du navigateur.
 */
export function flattenTree(rows, expanded) {
    const flat = [];
    for (const row of rows || []) {
        if (row.kind !== "attribute") {
            flat.push({...row, depth: 0});
            continue;
        }
        const isOpen = expanded.has(row.id);
        flat.push({...row, depth: 0, expanded: isOpen, hasValues: (row.values || []).length > 0});
        if (!isOpen) {
            continue;
        }
        for (const value of row.values || []) {
            flat.push({...value, depth: 1});
        }
    }
    return flat;
}

export class ConfiguratorTree extends Component {
    static template = "product_configurator_fa.ConfiguratorTree";
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({rows: [], expanded: new Set()});
        this.rootRef = useRef("root");
        useSortable({
            ref: this.rootRef,
            // ⚠️ Seules les lignes d'ATTRIBUT portent cette classe : un bandeau
            // d'étape n'est pas un enregistrement, et une valeur suit le sien.
            elements: ".o_config_attribute",
            handle: ".o_config_handle",
            cursor: "grabbing",
            // ⚠️ **LE FANTÔME LAISSÉ EN PLACE EST UN `<tr>` MIS EN BLOC.** Le
            // cœur clone la ligne emportée et lui pose `display: block` en
            // style en ligne (`sortable.js`) : dans un tableau, une rangée en
            // bloc quitte la grille des colonnes, et le tableau se retaille
            // sans elle. `d-table-row` est un utilitaire Bootstrap, donc
            // `!important` : c'est ce qui lui reprend la main. Le cœur fait
            // exactement cela pour ses listes (`list_renderer.js`).
            placeholderClasses: ["d-table-row"],
            onDragStart: ({element}) => this.freezeCellWidths(element),
            onDragEnd: ({element}) => this.releaseCellWidths(element),
            onDrop: ({element, previous}) => this.onDrop(element, previous),
        });
        // ⚠️ **DEUX ORDRES, DONC DEUX POIGNÉES.** Les valeurs vivent dans le même
        // `<tbody>` que leurs attributs : aucun élément du DOM ne les regroupe,
        // et l'option `groups` du cœur en réclamerait un. C'est donc la POIGNÉE
        // qui sépare les deux glissers — le cœur ne démarre une séquence que si
        // le clic tombe dans `elements handle` (`draggable_hook_builder.js`).
        // Le refus d'un dépôt hors de son attribut, lui, se joue au dépôt.
        useSortable({
            ref: this.rootRef,
            elements: ".o_config_value",
            handle: ".o_config_value_handle",
            cursor: "grabbing",
            placeholderClasses: ["d-table-row"],
            onDragStart: ({element}) => this.freezeCellWidths(element),
            onDragEnd: ({element}) => this.releaseCellWidths(element),
            onDrop: ({element, previous}) => this.onDropValue(element, previous),
        });
        onWillStart(() => this.load());
        // ⚠️ L'arbre est lu du SERVEUR, pas du cache du formulaire : il joint
        // trois modèles. Il doit donc se relire quand l'enregistrement change,
        // sans quoi il montrerait l'état d'avant la dernière sauvegarde.
        onWillUpdateProps(() => this.load());
    }

    get templateId() {
        return this.props.record.resId;
    }

    async load() {
        if (!this.templateId) {
            this.state.rows = [];
            return;
        }
        this.state.rows = await this.orm.call(
            "product.template", "get_configurator_tree", [[this.templateId]]
        );
    }

    get rows() {
        return flattenTree(this.state.rows, this.state.expanded);
    }

    toggle(row) {
        if (this.state.expanded.has(row.id)) {
            this.state.expanded.delete(row.id);
        } else {
            this.state.expanded.add(row.id);
        }
        // `Set` n'est pas réactif par mutation : on le remplace pour que OWL voie.
        this.state.expanded = new Set(this.state.expanded);
    }

    /** Les identifiants de lignes d'attribut, dans l'ordre affiché. */
    get lineIds() {
        return (this.state.rows || [])
            .filter((row) => row.kind === "attribute")
            .map((row) => row.id);
    }

    /**
     * Fige les COLONNES du tableau, le temps d'un glisser.
     *
     * ⚠️ **LE TABLEAU SE REDESSINE DÈS QU'ON LUI RETIRE UNE RANGÉE.** Il est en
     * `table-layout: auto` : ses colonnes se mesurent sur leur contenu, et la
     * rangée emportée — passée en `position: fixed` — n'en fait plus partie. Ce
     * sont donc TOUTES les lignes restantes qui glissent latéralement, pas
     * seulement celle qu'on tire. C'est ce que Gerry a vu sur le JeNo 5".
     *
     * ⚠️ **AU POINTERDOWN, ET PAS PLUS TARD.** Le cœur pose `position: fixed`
     * AVANT d'appeler `onDragStart` (`draggable_hook_builder.js`) : mesurer
     * là-bas, ce serait déjà mesurer le tableau d'après.
     */
    freezeColumns() {
        const table = this.rootRef.el;
        if (!table || table.dataset.frozenColumns) {
            return;
        }
        for (const entete of table.querySelectorAll("thead th")) {
            entete.style.width = `${entete.getBoundingClientRect().width}px`;
        }
        table.style.tableLayout = "fixed";
        table.dataset.frozenColumns = "1";
        // ⚠️ Un simple CLIC sur la poignée ne démarre aucun glisser : `onDragEnd`
        // ne viendrait jamais, et le tableau resterait figé sur des largeurs
        // périmées dès le prochain redimensionnement de la fenêtre.
        window.addEventListener("pointerup", () => this.releaseColumns(), {once: true});
    }

    /** Rend le tableau à sa mise en page souple. */
    releaseColumns() {
        const table = this.rootRef.el;
        if (!table) {
            return;
        }
        for (const entete of table.querySelectorAll("thead th")) {
            entete.style.width = "";
        }
        table.style.tableLayout = "";
        delete table.dataset.frozenColumns;
    }

    /**
     * Fige la largeur des cellules de la ligne qu'on emporte.
     *
     * ⚠️ **UNE RANGÉE TIRÉE QUITTE SON TABLEAU.** Le cœur lui pose
     * `position: fixed` : ses cellules n'ont plus de colonnes auxquelles
     * s'aligner et se retaillent sur leur contenu. Le texte de la ligne tirée
     * glisserait alors, même une fois les colonnes du tableau figées.
     *
     * ⓘ La mesure vient de l'EN-TÊTE, pas de la cellule : c'est l'en-tête qui
     * porte la largeur de colonne — et il est FIGÉ depuis `freezeColumns`, donc
     * il dit encore la largeur d'avant le glisser. Même remède que le cœur pour
     * ses listes (`list_renderer.js`, `sortStart`).
     */
    freezeCellWidths(element) {
        const entetes = [...this.rootRef.el.querySelectorAll("thead th")];
        let colonne = 0;
        for (const cellule of element.querySelectorAll("td")) {
            let largeur = 0;
            // ⓘ Une cellule peut couvrir plusieurs colonnes : on additionne.
            for (let i = 0; i < cellule.colSpan; i++) {
                const entete = entetes[colonne + i];
                if (entete) {
                    largeur += parseFloat(getComputedStyle(entete).width);
                }
            }
            cellule.style.width = `${largeur}px`;
            colonne += cellule.colSpan;
        }
    }

    /**
     * Rend les cellules à la mise en page du tableau.
     *
     * ⚠️ Sur `onDragEnd`, pas sur `onDrop` : un déplacement ABANDONNÉ ne passe
     * pas par `onDrop`, et la ligne resterait figée sur des largeurs qui ne
     * valent plus rien dès que la fenêtre change.
     */
    releaseCellWidths(element) {
        for (const cellule of element.querySelectorAll("td")) {
            cellule.style.width = null;
        }
        this.releaseColumns();
    }

    /** Les identifiants des valeurs d'un attribut, dans l'ordre affiché. */
    valueIds(lineId) {
        const ligne = (this.state.rows || []).find(
            (row) => row.kind === "attribute" && row.id === lineId
        );
        return ((ligne && ligne.values) || []).map((valeur) => valeur.id);
    }

    /**
     * La ligne d'attribut au-dessus du point de dépôt.
     *
     * ⚠️ **LE VOISIN N'EST PAS FORCÉMENT UN ATTRIBUT.** Il peut être un bandeau
     * d'étape — qui ne porte aucun identifiant, puisqu'il n'est pas un
     * enregistrement (D-202) — ou une VALEUR, qui porte l'identifiant de son
     * attribut : déposer sous la dernière valeur de X, c'est bien déposer
     * sous X. On remonte donc jusqu'à la première ligne qui dise quelque chose.
     *
     * ⓘ `null` veut dire « rien au-dessus » : dépôt en tête.
     */
    previousLineId(node) {
        let curseur = node;
        while (curseur && !curseur.dataset.lineId) {
            curseur = curseur.previousElementSibling;
        }
        return curseur ? Number(curseur.dataset.lineId) : null;
    }

    /**
     * La valeur au-dessus du point de dépôt — DANS le même attribut.
     *
     * ⚠️ **UNE VALEUR NE CHANGE PAS D'ATTRIBUT EN GLISSANT.** Rien dans le DOM
     * ne l'en empêche : toutes les lignes partagent un `<tbody>`, et l'option
     * `groups` du cœur réclamerait un élément parent par groupe. Le refus se
     * joue donc ici — `-1`, que `dropIndex` puis `reorder` traitent comme un
     * non-mouvement.
     *
     * ⓘ `null` quand le voisin est la ligne d'ATTRIBUT elle-même : la valeur
     * passe en tête de son bloc.
     */
    previousValueId(node, lineId) {
        if (!node || Number(node.dataset.lineId) !== lineId) {
            return -1;
        }
        return node.dataset.valueId ? Number(node.dataset.valueId) : null;
    }

    async onDrop(element, previous) {
        const moved = Number(element.dataset.lineId);
        const ids = this.lineIds;
        const from = ids.indexOf(moved);
        const ordonne = reorder(ids, from, dropIndex(ids, from, this.previousLineId(previous)));
        await this.orm.call(
            "product.template", "configurator_reorder", [[this.templateId], ordonne]
        );
        await this.load();
    }

    /**
     * ⚠️ **CET ORDRE APPARTIENT À L'ATTRIBUT, PAS AU PRODUIT** — arbitré par
     * Gerry le 2026-08-29. Une valeur est un `product.attribute.value` et son
     * rang vit dans sa `sequence` : la déplacer ici la déplace sur tous les
     * produits qui emploient cet attribut. C'est le seul ordre qui existe — en
     * inventer un par produit obligerait tout ce qui affiche des valeurs à le
     * relire.
     */
    async onDropValue(element, previous) {
        const lineId = Number(element.dataset.lineId);
        const moved = Number(element.dataset.valueId);
        const ids = this.valueIds(lineId);
        const from = ids.indexOf(moved);
        const to = dropIndex(ids, from, this.previousValueId(previous, lineId));
        if (to < 0) {
            // Dépôt hors de son attribut : le cœur n'a rien touché au DOM
            // (`applyChangeOnDrop` est faux), la ligne est déjà revenue seule.
            return;
        }
        await this.orm.call(
            "product.template", "configurator_reorder_values",
            [[this.templateId], lineId, reorder(ids, from, to)]
        );
        await this.load();
    }

    async removeFacet(row, facet) {
        await this.orm.call(
            "product.template", "configurator_remove_facet", [[this.templateId], facet.id]
        );
        await this.load();
    }

    async removeRow(row) {
        if (row.kind === "step") {
            await this.orm.call(
                "product.template", "configurator_clear_step",
                [[this.templateId], row.line_id]
            );
        } else if (row.kind === "value") {
            await this.orm.call(
                "product.template", "configurator_remove_value",
                [[this.templateId], row.line_id, row.id]
            );
        } else {
            await this.orm.call("product.template.attribute.line", "unlink", [[row.id]]);
        }
        await this.load();
    }

    /**
     * ⚠️ L'ARBRE VIDE DOIT DIRE QUOI FAIRE. Une liste sans ligne et sans point
     * d'entrée n'est pas « vide » : elle est cassée, du point de vue de qui la
     * regarde. Constaté à l'écran par Gerry sur un produit sans attribut.
     */
    get isEmpty() {
        return !(this.state.rows || []).length;
    }

    async addAttribute() {
        const action = await this.orm.call(
            "product.template", "action_configurator_add_attribute", [[this.templateId]]
        );
        this.action.doAction(action, {onClose: () => this.load()});
    }

    async addStep() {
        const action = await this.orm.call(
            "product.template", "action_configurator_add_step", [[this.templateId]]
        );
        this.action.doAction(action, {onClose: () => this.load()});
    }

    /**
     * ⚠️ La cellule « Conditions » s'ouvre même VIDE : c'est par elle qu'on en
     * pose une. Sans cela, retirer « Configuration Restrictions » aurait retiré
     * le seul endroit d'où l'on crée une condition par valeur.
     */
    async openCondition(row) {
        const action = await this.orm.call(
            "product.template", "configurator_open_condition",
            [[this.templateId], row.kind === "value" ? row.line_id : row.id,
             row.kind === "value" ? row.id : false]
        );
        this.action.doAction(action, {onClose: () => this.load()});
    }

    async openStep(row) {
        const action = await this.orm.call(
            "product.template", "configurator_open_step", [[this.templateId], row.line_id]
        );
        if (action) {
            this.action.doAction(action, {onClose: () => this.load()});
        }
    }

    /**
     * ⚠️ Les réglages d'une ligne — mode de prix, bornes, rôle de dimension, vue
     * 3D — n'étaient joignables NULLE PART depuis la fiche produit : le bouton
     * « Configurer » du cœur ouvre les valeurs, pas la ligne. Le nom de
     * l'attribut devient donc la porte de ses réglages.
     */
    async openLine(row) {
        const action = await this.orm.call(
            "product.template.attribute.line", "action_open_configurator_line",
            [[row.id]]
        );
        this.action.doAction(action, {onClose: () => this.load()});
    }

    async openValues(row) {
        const action = await this.orm.call(
            "product.template.attribute.line", "action_open_values", [[row.id]]
        );
        this.action.doAction(action, {onClose: () => this.load()});
    }
}

export const configuratorTreeField = {
    component: ConfiguratorTree,
    supportedTypes: ["one2many"],
};

registry.category("fields").add("configurator_tree", configuratorTreeField);
