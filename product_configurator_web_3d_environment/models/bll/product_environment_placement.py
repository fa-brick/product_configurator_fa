"""Ce qu'exécute `product.environment.placement` (BLL, D-541)."""
from odoo import models


class ProductEnvironmentPlacement(models.Model):
    _inherit = "product.environment.placement"

    def init(self):
        # ⚠️ « Une baie, un produit » vaut par MONTAGE, et un chantier en porte un par devis (E-1) :
        # l'ancienne contrainte SQL sur (environnement, baie) refuserait le second devis. Odoo ne
        # retire pas une contrainte qu'on cesse de déclarer : on la retire ici (D-426).
        self.env.cr.execute("ALTER TABLE product_environment_placement DROP CONSTRAINT IF EXISTS "
                            "product_environment_placement_one_per_bay")

    def editor_entry(self):
        """Ce que l'éditeur lit d'un placement."""
        self.ensure_one()
        session = self.session_id.sudo()
        return {
            "openingId": self.opening_id,
            "productId": self.product_tmpl_id.id,
            "productName": self.product_tmpl_id.display_name,
            "token": session.access_token if session else None,
            # ⓘ L'écart à la baie, que le produit garde quand la baie change (D-424).
            "offsets": self.environment_id._placement_offsets(self),
        }
