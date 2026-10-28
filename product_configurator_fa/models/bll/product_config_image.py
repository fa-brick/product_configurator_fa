"""Ce qu'exécute `product.config.image` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductConfigImage(models.Model):
    _inherit = "product.config.image"

    @api.constrains("value_ids")
    def _check_value_ids(self):
        """Check combination of values is possible according to given
        restrictions on linked product template"""
        cfg_session_obj = self.env["product.config.session"]
        for cfg_img in self:
            try:
                cfg_session_obj.validate_configuration(
                    value_ids=cfg_img.value_ids.ids,
                    product_tmpl_id=cfg_img.product_tmpl_id.id,
                    final=False,
                )
            except ValidationError as exc:
                raise ValidationError(
                    self.env._(
                        "Values entered for line '%s' generate "
                        "a incompatible configuration",
                        cfg_img.name,
                    )
                ) from exc
