"""Ce qu'exécute `sale.order` (BLL, D-541)."""
from odoo import _, models
from odoo.tools.safe_eval import safe_eval


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_open_montage(self):
        """Le bouton « Montage » du devis : l'éditeur de son environnement, sur SES placements, en pleine page.

        ⚠️ Le DEVIS voyage par `active_id`, et son action dit `active_model` : au rechargement, l'éditeur
        redemande le montage de CE devis, pas l'environnement nu (8.5b, W-113 E-2a).
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "product_configurator_web_3d_environment_sale.environment_montage_client_action")
        params = self.editor_open_params()
        action.update({
            "name": params["title"], "display_name": params["title"],
            # ⚠️ `_for_xml_id` rend le contexte de l'action en TEXTE : le compléter tel quel lève.
            "context": {**safe_eval(action.get("context") or "{}"), "active_id": self.id},
            "params": params,
        })
        return action

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

    def editor_open_params(self):
        """Le jeton du DEVIS et l'état de son montage — ce que l'action pleine page redemande au rechargement."""
        self.ensure_one()
        self._portal_ensure_token()
        environment = self.environment_id.with_context(environment_order_id=self.id)
        return {"token": self.access_token, "state": environment.editor_state(),
                "title": _("Montage of %s", self.name)}
