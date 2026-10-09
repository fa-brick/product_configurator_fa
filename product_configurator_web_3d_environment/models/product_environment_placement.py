# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ProductEnvironmentPlacement(models.Model):
    """Un produit POSÉ dans une baie d'un environnement (W-111, étape 8.4c).

    ⓘ La baie est une donnée de l'environnement ([[D-418]]) ; ce qui y est posé, avec sa
    configuration, vit ici. Le montage d'un devis (étape 8.5) s'appuiera sur ces placements.
    ⚠️ Une baie, un produit (v1) : en reposer un autre REMPLACE le premier.
    """
    _name = "product.environment.placement"
    _description = "Product placed in an environment bay"
    _order = "id"

    environment_id = fields.Many2one("product.environment", required=True, ondelete="cascade", index=True)
    opening_id = fields.Char(string="Bay", required=True, help="Identifier of the bay in the plan.")
    product_tmpl_id = fields.Many2one("product.template", string="Product", required=True, ondelete="cascade")
    # ⓘ Vide pour un produit qui ne se configure pas : il est posé tel quel.
    session_id = fields.Many2one("product.config.session", string="Configuration", ondelete="set null")

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
