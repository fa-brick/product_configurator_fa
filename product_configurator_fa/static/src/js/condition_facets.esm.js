/**
 * Une condition se lit comme une BARRE DE RECHERCHE — B2, D-203.
 *
 * Constat de Gerry : « regarde comment fonctionnent les pastilles avec la barre
 * de recherche, je voudrais le même fonctionnement ». Sa sémantique tombe juste
 * sur le stockage existant : ET entre les pastilles, OU à l'intérieur d'une.
 *
 * ⚠️ **CE WIDGET NE MODIFIE RIEN — il LIT.** L'édition reste le formulaire de
 * condition, qui manipule des ENREGISTREMENTS (D-080). Reconstruire la condition
 * depuis un texte de pastilles serait revenir au stockage textuel que ce dépôt a
 * écarté, et le perdre en silence.
 *
 * ⓘ Il s'appuie sur `condition_summary`, calculé côté serveur : un widget posé
 * sur un Many2one ne reçoit que l'identifiant et le nom de sa cible, jamais ses
 * champs. Le résumé est donc remonté sur la ligne, et déclaré dans la vue.
 */
import {Many2OneField, many2OneField} from "@web/views/fields/many2one/many2one_field";
import {registry} from "@web/core/registry";

/** Ce que le serveur intercale entre deux pastilles (`FACET_SEPARATOR`). */
export const FACET_SEPARATOR = " • ";

/**
 * Découpe un résumé en pastilles.
 *
 * ⚠️ Un résumé vide ne donne PAS une pastille vide : `"".split(sep)` rend
 * `[""]`, et l'écran afficherait une pastille sans texte là où il n'y a aucune
 * condition. C'est le cas le plus fréquent — la plupart des lignes n'en portent
 * pas.
 */
export function splitFacets(summary) {
    if (!summary) {
        return [];
    }
    return summary.split(FACET_SEPARATOR).filter((facet) => facet.length);
}

export class ConditionFacets extends Many2OneField {
    static template = "product_configurator_fa.ConditionFacets";

    get facets() {
        return splitFacets(this.props.record.data[this.props.summaryField]);
    }

    get hasCondition() {
        return this.facets.length > 0;
    }
}

ConditionFacets.props = {
    ...Many2OneField.props,
    summaryField: {type: String},
};

export const conditionFacetsField = {
    ...many2OneField,
    component: ConditionFacets,
    extractProps(fieldInfo, dynamicInfo) {
        const props = many2OneField.extractProps(fieldInfo, dynamicInfo);
        // Le champ qui porte le résumé se déclare dans la vue : deux lignes
        // différentes (restriction, étape) portent chacune le leur.
        props.summaryField = fieldInfo.options.summary_field;
        return props;
    },
    fieldDependencies: [{name: "display_name", type: "char"}],
};

registry.category("fields").add("condition_facets", conditionFacetsField);
