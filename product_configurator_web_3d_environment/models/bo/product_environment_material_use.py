"""Ce que déclare `product.environment.material.use` (BO, D-541)."""
from odoo import fields, models


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
