# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ⓘ L'environnement que le MONTAGE de ce devis lit (E-1) ; un devis dupliqué n'emporte pas de montage.
    environment_id = fields.Many2one("product.environment", string="Environment", copy=False, index=True)
    environment_placement_ids = fields.One2many("product.environment.placement", "order_id", string="Montage")

    def _action_confirm(self):
        """La COMMANDE reçoit sa copie gelée de l'environnement (Q-12.6) : le projet du client
        redevient libre pour un nouveau montage, et rien ne touche plus ce qui est commandé."""
        result = super()._action_confirm()
        # ⚠️ En `sudo` : au portail, c'est le CLIENT qui accepte le devis, sans droit sur les placements.
        for order in self.sudo().filtered("environment_id"):
            environment = order.environment_id
            # ⓘ Une copie déjà propre à ce devis (8.5c), que personne d'autre ne lit, est déjà gelée.
            if environment.source_environment_id and not (environment.order_ids - order):
                continue
            environment._copy_for_order(order)
        return result

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
