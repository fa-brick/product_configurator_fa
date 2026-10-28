"""Ce qu'exécute `product.attribute.value.line` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductAttributeValueLine(models.Model):
    _inherit = "product.attribute.value.line"

    @api.constrains("value_ids")
    def _validate_configuration(self):
        """Ensure that the passed configuration in value_ids is a valid"""
        cfg_session_obj = self.env["product.config.session"]
        for attr_val_line in self:
            value_ids = attr_val_line.value_ids.ids
            value_ids.append(attr_val_line.value_id.id)
            valid = cfg_session_obj.validate_configuration(
                value_ids=value_ids,
                product_tmpl_id=attr_val_line.product_tmpl_id.id,
                final=False,
            )
            if not valid:
                raise ValidationError(
                    self.env._(
                        "Values provided to the attribute value line are "
                        "incompatible with the current rules"
                    )
                )
