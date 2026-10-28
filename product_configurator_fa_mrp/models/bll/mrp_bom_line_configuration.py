"""Ce qu'exécute `mrp.bom.line.configuration` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class MrpBomLineConfiguration(models.Model):
    _inherit = "mrp.bom.line.configuration"

    @api.constrains("value_ids")
    def _check_no_variant_values(self):
        """Une condition de nomenclature ne cite pas de réponse « sans variante » — W-99 / D-393.

        ⚠️ Elle se compare aux valeurs de l'ARTICLE (`create_get_bom`), et depuis l'option A une
        réponse « sans variante » n'y entre plus : la condition ne jouerait JAMAIS, sans un mot.
        Même raison que le refus d'un composant « sans variante » (D-393, Q1) : la nomenclature
        est bâtie par article.
        """
        for config in self:
            no_variant = config.value_ids.filtered(
                lambda v: v.attribute_id.create_variant == "no_variant")
            if no_variant:
                raise ValidationError(self.env._(
                    "A bill of materials condition cannot use answers that create no variant "
                    "(%s): it is matched against the configured product, which does not carry "
                    "them.", ", ".join(no_variant.mapped("display_name"))))
