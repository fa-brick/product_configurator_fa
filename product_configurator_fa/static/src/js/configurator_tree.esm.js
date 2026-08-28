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
            onDrop: ({element, previous}) => this.onDrop(element, previous),
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

    async onDrop(element, previous) {
        const moved = Number(element.dataset.lineId);
        const ids = this.lineIds;
        const from = ids.indexOf(moved);
        // `previous` est la ligne au-dessus du point de dépôt ; sans elle, on
        // dépose en tête.
        const previousId = previous ? Number(previous.dataset.lineId) : null;
        const to = previousId === null ? 0 : ids.indexOf(previousId) + (from < ids.indexOf(previousId) ? 0 : 1);
        const ordonne = reorder(ids, from, to);
        await this.orm.call(
            "product.template", "configurator_reorder", [[this.templateId], ordonne]
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
