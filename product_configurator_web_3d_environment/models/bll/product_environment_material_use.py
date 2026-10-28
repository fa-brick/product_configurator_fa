"""Ce qu'exécute `product.environment.material.use` (BLL, D-541)."""
from odoo import api, models
from odoo.addons.product_configurator_web_3d.models.bll.product_attribute import IMAGE_FORMS, SUMMARY_FORMS


class ProductEnvironmentMaterialUse(models.Model):
    _inherit = "product.environment.material.use"

    @api.model
    def _selection_display_type(self):
        # ⚠️ Pas de cases multiples : une surface porte UNE matière, une seconde case cochée n'aurait pas de sens.
        return [(key, label) for key, label in self._attribute_selection("display_type") if key != "multi"]

    @api.model
    def _selection_swatch_mark(self):
        return self._attribute_selection("swatch_mark")

    @api.model
    def _selection_answer_size(self):
        return self._attribute_selection("answer_size")

    @api.model
    def _selection_answer_layout(self):
        return self._attribute_selection("answer_layout")

    @api.model
    def _attribute_selection(self, name):
        return self.env["product.attribute"]._fields[name]._description_selection(self.env)

    def _web_answer_layout(self):
        """La disposition EFFECTIVE — le même calcul que celui d'un attribut (`_web_answer_layout`, D-382)."""
        self.ensure_one()
        layout = self.answer_layout or "inline"
        if layout in ("scroll", "line") and self.display_type not in IMAGE_FORMS:
            return "inline"
        if layout == "summary" and self.display_type not in SUMMARY_FORMS:
            return "inline"
        return layout

    def js_row(self, materials):
        row = super().js_row(materials)
        row.update(displayType=self.display_type, swatchMark=self.swatch_mark, answerSize=self.answer_size,
                   answerLayout=self._web_answer_layout(), answerLayoutSet=self.answer_layout)
        return row
