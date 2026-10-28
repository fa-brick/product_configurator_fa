"""Ce qu'exécute `product.config.line` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductConfigLine(models.Model):
    _inherit = "product.config.line"

    @api.depends(
        "attribute_line_id.value_ids",
        "attribute_line_id.attribute_id.val_custom",
    )
    def _compute_attr_line_val_ids(self):
        for config_line in self:
            config_line.attr_line_val_ids = (
                config_line.attribute_line_id._configurator_value_ids()
            )

    # TODO: Prevent config lines having dependencies that are not set in other
    # config lines
    # TODO: Prevent circular depdencies: Length -> Color, Color -> Length
    @api.onchange("attribute_line_id")
    def onchange_attribute(self):
        self.value_ids = False
        self.domain_id = False

    @api.constrains("value_ids")
    def check_value_attributes(self):
        """Values selected in config lines must be allowed."""
        for line in self:
            forbidden_values = line.value_ids - line.attr_line_val_ids
            if forbidden_values:
                raise ValidationError(
                    self.env._(
                        "Values must belong to the attribute of the "
                        "corresponding attribute_line set on the "
                        "configuration line"
                    )
                )
