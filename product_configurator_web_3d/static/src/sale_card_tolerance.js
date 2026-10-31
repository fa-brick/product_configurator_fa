/** @odoo-module **/
/**
 * Le dialogue de vente d'Odoo dessine la carte et la grande pastille comme le configurateur — D-258, D-563.
 *
 * ⚠️ `ProductTemplateAttributeLine` (Odoo 18) VALIDE `display_type` contre une liste fermée : une forme d'ici y est
 * refusée en mode développeur (D-258).
 * ⚠️ Son `switch` n'a pas de `default` : une forme inconnue rend `undefined` à `t-call`, et le dialogue entier
 * tombe (D-258).
 * ⚠️ Chargé au back-office ET au site (`product_configurator_web_sale`) : sans lui, le dialogue des options du site
 * tombait sur une carte (D-563).
 * ⓘ Le dessin vient de `configurator_page.scss` ; l'état choisi se lit sur le bouton radio coché (D-563).
 */
import { formatCurrency } from "@web/core/currency";
import { patch } from "@web/core/utils/patch";
import {
    ProductTemplateAttributeLine,
} from "@sale/js/product_template_attribute_line/product_template_attribute_line";

const IMAGE_FORMS = {
    card: "product_configurator_web_3d.ptav_card",
    swatch: "product_configurator_web_3d.ptav_swatch",
};

// La validation d'abord : elle refuse la valeur avant même que le gabarit soit choisi.
const displayType = ProductTemplateAttributeLine.props.attribute.shape.display_type;
const acceptedBefore = displayType.validate;
displayType.validate = (type) => type === "card" || type === "swatch" || acceptedBefore(type);

// ⚠️ Les clés servies par `SaleProductConfiguratorImageForms` : un `shape` refuse toute clé qu'il ne nomme pas.
Object.assign(ProductTemplateAttributeLine.props.attribute.shape, {
    swatch_mark: { type: String, optional: true },
    answer_size: { type: String, optional: true },
});
Object.assign(ProductTemplateAttributeLine.props.attribute_values.element.shape, {
    preview: { type: [Boolean, String], optional: true },
});

patch(ProductTemplateAttributeLine.prototype, {
    getPTAVTemplate() {
        return IMAGE_FORMS[this.props.attribute.display_type]
            || super.getPTAVTemplate(...arguments)
            || "sale.ptav_pills";
    },

    /** Les classes de la grille d'une forme à image : la taille, et la marque d'une grande pastille. */
    imageFormGridClass() {
        const { display_type, answer_size, swatch_mark } = this.props.attribute;
        const size = answer_size || "medium";
        return display_type === "swatch"
            ? `o_cfg3d_bigswatches--${swatch_mark || "check"} o_cfg3d_bigswatches--${size}`
            : `o_cfg3d_cards--${size}`;
    },

    /** Le montant du supplément, sans signe : le badge du configurateur les sépare. */
    extraAmount(ptav) {
        return formatCurrency(Math.abs(ptav.price_extra), this.env.currency.id);
    },
});
