"""Ce que déclare `report.product_configurator_web_3d_sale_drawing.pages` (BO, D-541)."""
# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class DrawingPageReport(models.AbstractModel):
    # ⚠️ Un nom COURT : la table du modèle, `report_<module>_<gabarit>`, ne dépasse pas 63 caractères.
    _name = "report.product_configurator_web_3d_sale_drawing.pages"
    _description = "Dimensioned drawing pages"
