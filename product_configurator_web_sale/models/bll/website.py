"""Ce qu'exécute `website` (BLL, D-541).

Le texte du bouton qui ouvre le configurateur — D-558.
"""
from odoo import models


class Website(models.Model):
    _inherit = "website"

    def _configure_button_label(self):
        """Le texte réglé pour ce site, dans la langue du visiteur, sinon « Configure » traduit.

        ⚠️ Un seul texte pour les trois boutons (fiche, grille, liste de souhaits) : le même geste garde le même mot (D-558).
        """
        self.ensure_one()
        return self.configure_button_text or self.env._("Configure")
