"""Ce que déclare `product.configurator.condition` (BO, D-541)."""
from odoo import fields, models


class ProductConfiguratorCondition(models.TransientModel):
    _inherit = "product.configurator.condition"

    # ⚠️ **UN CHAMP, PAS LE CONTEXTE.** L'assistant est rouvert par le CLIENT au moment
    # de valider : il appelle `action_confirm` sur l'enregistrement, avec le contexte de
    # l'action et non celui de la création. Une cible posée dans le contexte de `create`
    # n'aurait donc pas survécu au premier clic — et la condition serait partie écraser
    # un `product.config.domain` inexistant, sans rien dire.
    component_id = fields.Many2one(
        comodel_name="product.model3d.component", readonly=True,
        string="Placement",
    )
