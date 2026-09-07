# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Ouvrir le configurateur 3D DEPUIS une ligne de devis — D-259.

Le commercial choisit un produit sur une ligne ; s'il est configurable, c'est
notre configurateur qui s'ouvre, en dialogue, sans quitter le devis. Le même
composant que la page publique : une seule implémentation des formes de
question, du moteur et de la scène.
"""
from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def web3d_open_configuration(self, session_id=None):
        """Préparer une configuration pour ce modèle, et rendre de quoi l'afficher.

        ⓘ **Le pendant back-office de `/configurator/prepare`**, et il rend
        exactement la même chose — jeton et état complet. Le dialogue n'a plus
        qu'à monter le composant, comme la page le fait.

        ⚠️ **`force_create=True`.** Une configuration ouverte depuis une ligne
        lui appartiendra : réutiliser le dernier brouillon du commercial
        rattacherait à cette ligne-ci une configuration déjà portée par une
        autre — le même raisonnement que pour la roue dentée.

        ⓘ `session_id` REPREND une configuration existante au lieu d'en ouvrir
        une neuve : c'est le cas « je rouvre la ligne pour la corriger ».
        """
        self.ensure_one()
        Session = self.env["product.config.session"]
        session = Session.browse(session_id).exists() if session_id else Session
        if not session:
            session = Session.create_get_session(self.id, force_create=True)
        session._ensure_access_token()
        return {
            "sessionId": session.id,
            "token": session.access_token,
            "state": session.web_state(),
        }
