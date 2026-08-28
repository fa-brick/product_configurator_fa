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
import {Component, onWillStart, onWillUpdateProps, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useService} from "@web/core/utils/hooks";

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
