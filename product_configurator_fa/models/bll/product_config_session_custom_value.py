"""Ce qu'exécute `product.config.session.custom.value` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductConfigSessionCustomValue(models.Model):
    _inherit = "product.config.session.custom.value"

    @api.depends("value", "attribute_id", "attribute_id.uom_id")
    def _compute_val_name(self):
        # La valeur est le NOMBRE, l'affichage porte l'unité — et la mise en
        # forme vient de l'attribut, pas d'ici : c'est la même partout.
        # ⚠️ `value` manquait au `depends` : renseigner une valeur ne
        # recalculait pas son libellé.
        for attr_val_custom in self:
            attr_val_custom.name = attr_val_custom.attribute_id.format_custom_value(
                attr_val_custom.value
            )

    @api.constrains("cfg_session_id", "attribute_id")
    def unique_attribute(self):
        for custom_val in self:
            values = custom_val.cfg_session_id.custom_value_ids
            if (
                len(
                    values.filtered(
                        lambda x, custom_val=custom_val: x.attribute_id
                        == custom_val.attribute_id
                    )
                )
                > 1
            ):
                raise ValidationError(
                    self.env._(
                        "Configuration cannot have the " "same value inserted twice"
                    )
                )

    @api.constrains("attachment_ids", "value")
    def check_custom_type(self):
        for custom_val in self:
            custom_type = custom_val.attribute_id.custom_type
            if custom_val.value and custom_type == "binary":
                raise ValidationError(
                    self.env._(
                        "Attribute custom type is binary, attachments are the "
                        "only accepted values with this custom field type"
                    )
                )
            if custom_val.attachment_ids and custom_type != "binary":
                raise ValidationError(
                    self.env._(
                        "Attribute custom type must be 'binary' for saving "
                        "attachments to custom value"
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Range le nombre sous sa forme canonique AVANT qu'il touche la base.

        Le faire à l'écriture et non à l'affichage est ce qui rend deux saisies
        de la même largeur ÉGALES : `2400` et `2400.0` ne doivent pas devenir
        deux valeurs distinctes le jour du rangement en valeur d'attribut
        (D-081).
        """
        for vals in vals_list:
            if "value" in vals and vals.get("attribute_id"):
                attribute = self.env["product.attribute"].browse(vals["attribute_id"])
                vals["value"] = attribute.canonical_custom_value(vals["value"])
        return super().create(vals_list)

    def write(self, vals):
        if "value" not in vals:
            return super().write(vals)
        # ⚠️ Un seul `vals` pour des attributs différents : la forme canonique
        # dépend de l'attribut, donc l'écriture se fait par groupe. Prendre
        # `self.attribute_id` sans grouper ne rendrait rien dès le second
        # attribut, et la mise en forme sauterait EN SILENCE.
        result = True
        for attribute, records in self.grouped("attribute_id").items():
            canonical = dict(
                vals, value=attribute.canonical_custom_value(vals["value"])
            )
            result = (
                super(ProductConfigSessionCustomValue, records).write(canonical)
                and result
            )
        return result

    def eval(self):
        """Return custom value evaluated using the related custom field type"""
        field_type = self.attribute_id.custom_type
        if field_type == "binary":
            vals = self.attachment_ids.mapped("datas")
            if len(vals) == 1:
                return vals[0]
            return vals
        elif field_type == "integer":
            return int(self.value)
        elif field_type == "float":
            return float(self.value)
        return self.value
