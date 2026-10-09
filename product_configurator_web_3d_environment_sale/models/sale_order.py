# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ⓘ L'environnement que le MONTAGE de ce devis lit (E-1) ; un devis dupliqué n'emporte pas de montage.
    environment_id = fields.Many2one("product.environment", string="Environment", copy=False, index=True)
    environment_placement_ids = fields.One2many("product.environment.placement", "order_id", string="Montage")

    def action_open_montage(self):
        """Le bouton « Montage » du devis : l'éditeur de son environnement, sur SES placements (8.5b)."""
        self.ensure_one()
        self._portal_ensure_token()
        environment = self.environment_id.with_context(environment_order_id=self.id)
        return {
            "type": "ir.actions.client",
            "tag": "product_editor_environment.editor",
            "name": _("Montage of %s", self.name),
            "target": "new",
            "context": {"footer": False, "dialog_size": "extra-large"},
            "params": {"token": self.access_token, "state": environment.editor_state()},
        }
