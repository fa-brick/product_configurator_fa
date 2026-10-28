"""Ce qu'exécute `product.config.step.line` (BLL, D-541)."""
from odoo import models


class ProductConfigStepLine(models.Model):
    _inherit = "product.config.step.line"

    # ⓘ Les crochets du cœur, remplis ici — la colonne « Vue 3D » de l'arbre (D-386).
    def _configurator_camera_name(self):
        self.ensure_one()
        return self.view_camera_id.display_name or ""

    def _configurator_camera_id(self):
        self.ensure_one()
        return self.view_camera_id.id or False

    def _configurator_set_camera(self, camera_id):
        self.ensure_one()
        self.view_camera_id = self.product_tmpl_id._configurator_camera_of(camera_id)
