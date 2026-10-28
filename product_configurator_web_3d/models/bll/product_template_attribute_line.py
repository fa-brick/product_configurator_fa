"""Ce qu'exécute `product.template.attribute.line` (BLL, D-541)."""
from odoo import models


class ProductAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"

    def _configurator_camera_name(self):
        """Le crochet du cœur, rempli ici — la caméra est une fiche de l'éditeur."""
        self.ensure_one()
        return self.view_camera_id.display_name or ""

    def _configurator_camera_id(self):
        self.ensure_one()
        return self.view_camera_id.id or False

    def _configurator_set_camera(self, camera_id):
        """Posée depuis la liste déroulante de l'arbre (D-386)."""
        self.ensure_one()
        self.view_camera_id = self.product_tmpl_id._configurator_camera_of(camera_id)
