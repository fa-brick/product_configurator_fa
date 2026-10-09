# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Le montage d'un devis, par les jetons (W-111, étapes 8.5a-b).

ⓘ Le jeton d'un DEVIS ouvre son montage (8.5b) : le même éditeur, sur l'environnement que le devis lit,
avec ses seuls placements — le jeton reste la seule identité (D-190).
"""
from odoo import http
from odoo.http import request

from odoo.addons.product_editor_environment.controllers.main import EnvironmentEditorController


class EnvironmentQuoteController(EnvironmentEditorController):

    def _environment(self, token):
        environment = super()._environment(token)
        if environment or not token or not isinstance(token, str):
            return environment
        order = request.env["sale.order"].sudo().search(
            [("access_token", "=", token), ("environment_id", "!=", False)], limit=1)
        if not order:
            return environment
        environment = order.environment_id.with_context(environment_order_id=order.id)
        lang = request.cookies.get("frontend_lang")
        if lang and lang in dict(request.env["res.lang"].get_installed()):
            environment = environment.with_context(lang=lang)
        return environment

    @http.route("/environment/quote", type="json", auth="public", methods=["POST"], csrf=False)
    def quote(self, token=None, **kwargs):
        environment = self._environment(token)
        if not environment:
            return {"error": "unknown_environment"}
        if not environment._editor_can_write():
            return {"error": "read_only"}
        return environment.request_quote()
