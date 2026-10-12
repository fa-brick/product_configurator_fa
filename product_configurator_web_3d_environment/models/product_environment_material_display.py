# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""L'AFFICHAGE des listes de matières d'un environnement — celui d'un attribut (W-113, E-3c-3, D-451).

Chaque usage (mur extérieur, mur intérieur, sol) se montre dans la barre de droite comme une question de la page du
configurateur : même forme, même marque, même taille, même disposition, et rien de plus (§21.5).
"""
from odoo import api, fields, models

from odoo.addons.product_configurator_web_3d.models.product_attribute import IMAGE_FORMS, SUMMARY_FORMS

#: Ce que l'onglet Infos règle sur un usage : ses clés JS, et le champ de chacune.
DISPLAY_FIELDS = {"displayType": "display_type", "swatchMark": "swatch_mark", "answerSize": "answer_size",
                  "answerLayout": "answer_layout"}


class ProductEnvironmentMaterialUse(models.Model):
    _inherit = "product.environment.material.use"

    # ⚠️ Les valeurs sont LUES sur l'attribut : une forme ajoutée là-bas se propose ici, sans liste à tenir à jour.
    display_type = fields.Selection(selection="_selection_display_type", default="swatch", required=True,
                                    string="Display", help="The form of the materials, as for an attribute.")
    swatch_mark = fields.Selection(selection="_selection_swatch_mark", default="check", required=True,
                                   string="Selection mark")
    answer_size = fields.Selection(selection="_selection_answer_size", default="medium", required=True,
                                   string="Answer size")
    answer_layout = fields.Selection(selection="_selection_answer_layout", default="inline", required=True,
                                     string="Answer layout")

    @api.model
    def _attribute_selection(self, name):
        return self.env["product.attribute"]._fields[name]._description_selection(self.env)

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


class ProductEnvironment(models.Model):
    _inherit = "product.environment"

    def _material_use_values(self, values):
        vals = super()._material_use_values(values)
        if vals is None:
            return None
        Use = self.env["product.environment.material.use"]
        for key, name in DISPLAY_FIELDS.items():
            if key not in values:
                continue
            allowed = {value for value, _label in Use._fields[name]._description_selection(self.env)}
            if values[key] not in allowed:
                return None
            vals[name] = values[key]
        return vals

    def editor_state(self):
        state = super().editor_state()
        # ⓘ Les choix de l'onglet Infos, traduits — au back-office seulement, comme les catégories (Q-24.2).
        if state.get("can_set_material_uses"):
            Use = self.env["product.environment.material.use"]
            state["materialDisplayOptions"] = {
                key: [[value, label] for value, label in Use._fields[name]._description_selection(self.env)]
                for key, name in DISPLAY_FIELDS.items()
            }
        return state
