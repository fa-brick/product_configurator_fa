# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""« Mes environnements » au portail : les copies faites pour un devis n'y sont pas des chantiers (8.5c-d)."""
from odoo.addons.product_editor_environment.controllers.portal import EnvironmentPortal


class EnvironmentQuotePortal(EnvironmentPortal):

    def _environment_domain(self):
        return super()._environment_domain() + [("source_environment_id", "=", False)]
