# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Demander un devis depuis l'environnement, par son jeton (W-111, étape 8.5a)."""
from odoo import http

from odoo.addons.product_editor_environment.controllers.main import EnvironmentEditorController


class EnvironmentQuoteController(EnvironmentEditorController):

    @http.route("/environment/quote", type="json", auth="public", methods=["POST"], csrf=False)
    def quote(self, token=None, **kwargs):
        environment = self._environment(token)
        if not environment:
            return {"error": "unknown_environment"}
        if not environment._editor_can_write():
            return {"error": "read_only"}
        return environment.request_quote()
