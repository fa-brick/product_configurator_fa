# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La POSE d'un produit dans une baie, par le jeton de l'environnement (W-111, étape 8.4c)."""
from odoo import http

from odoo.addons.product_editor_environment.controllers.main import EnvironmentEditorController


class EnvironmentPlacementController(EnvironmentEditorController):

    @http.route("/environment/place", type="json", auth="public", methods=["POST"], csrf=False)
    def place(self, token=None, opening_id=None, product_tmpl_id=None, **kwargs):
        environment = self._environment(token)
        if not environment:
            return {"error": "unknown_environment"}
        if not environment._editor_can_write():
            return {"error": "read_only"}
        return environment.place_product(opening_id, product_tmpl_id)
