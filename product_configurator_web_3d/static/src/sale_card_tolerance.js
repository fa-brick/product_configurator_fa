/** @odoo-module **/
/**
 * Le dialogue d'Odoo ne CONNAÎT pas la carte — on l'empêche de tomber. D-258.
 *
 * ⚠️ **Ajouter une forme d'affichage engage les interfaces d'Odoo, qui l'ignorent
 * toutes.** `ProductTemplateAttributeLine` (Odoo 18) est le pire des trois cas
 * relevés : il **valide** `display_type` contre une liste fermée, puis choisit
 * son gabarit par un `switch` **sans `default`** — une carte y donne `undefined`
 * à `t-call`, et le dialogue entier tombe.
 *
 * ⓘ **Exposition réelle** : un attribut en carte posé sur un produit ORDINAIRE,
 * ouvert depuis un devis. Nos produits configurables, eux, passent par notre
 * dialogue (D-259) et ne traversent jamais ce composant.
 *
 * ⓘ **Pourquoi ici, et sans module-pont** : `sale` est déjà dans les dépendances
 * de ce module (`product_configurator_web_3d` → `product_editor` → `sale`,
 * vérifié le 2026-09-06). Le module qui AJOUTE la valeur est donc celui qui peut
 * — et doit — garder debout ce qui s'y ramifie.
 *
 * ⚠️ La carte retombe sur les PASTILLES, comme sur les pages du site
 * (`variants_card_fallback`) : une réponse visible sans image vaut mieux qu'une
 * question absente ou qu'un écran mort.
 */
import { patch } from "@web/core/utils/patch";
import {
    ProductTemplateAttributeLine,
} from "@sale/js/product_template_attribute_line/product_template_attribute_line";

// La validation d'abord : elle refuse la valeur avant même que le gabarit soit
// choisi, et le refus casse le rendu en mode développeur.
const forme = ProductTemplateAttributeLine.props.attribute.shape.display_type;
const acceptaitAvant = forme.validate;
forme.validate = (type) => type === "card" || acceptaitAvant(type);

patch(ProductTemplateAttributeLine.prototype, {
    getPTAVTemplate() {
        return super.getPTAVTemplate(...arguments) || "sale.ptav_pills";
    },
});
