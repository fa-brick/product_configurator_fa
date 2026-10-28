"""Ce qu'exécute `product.attribute.custom.value` (BLL, D-541)."""
from odoo import api, models


class ProductAttributeCustomValue(models.Model):
    _inherit = "product.attribute.custom.value"

    @api.depends(
        "custom_product_template_attribute_value_id.attribute_id.uom_id",
        "custom_product_template_attribute_value_id.attribute_id.custom_type",
    )
    def _compute_name(self):
        super()._compute_name()
        for record in self:
            attribute = record.custom_product_template_attribute_value_id.attribute_id
            if not attribute.uom_id or not record.custom_value:
                continue
            label = record.custom_product_template_attribute_value_id.display_name
            shown = attribute.format_custom_value(record.custom_value)
            record.name = f"{label}: {shown}" if label else shown

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ptav_id = vals.get("custom_product_template_attribute_value_id")
            if "custom_value" in vals and ptav_id:
                attribute = (
                    self.env["product.template.attribute.value"]
                    .browse(ptav_id)
                    .attribute_id
                )
                vals["custom_value"] = attribute.canonical_custom_value(
                    vals["custom_value"]
                )
        return super().create(vals_list)

    def write(self, vals):
        if "custom_value" not in vals:
            return super().write(vals)
        result = True
        for ptav, records in self.grouped(
            "custom_product_template_attribute_value_id"
        ).items():
            canonical = dict(
                vals,
                custom_value=ptav.attribute_id.canonical_custom_value(
                    vals["custom_value"]
                ),
            )
            result = (
                super(ProductAttributeCustomValue, records).write(canonical) and result
            )
        return result
