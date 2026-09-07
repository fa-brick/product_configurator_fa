# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Le CRAYON de la fiche produit ouvre la configuration 3D — arbitrage Gerry, 2026-09-05.

Le bouton ne change pas de place : il change de destination. Son dessin est
passé de la clé à molette au crayon le 2026-09-07, pour rejoindre l'icône
qu'Odoo emploie déjà sur la cellule produit d'une ligne de devis.
L'assistant OCA reste en vie pour les autres chemins (le bon de commande, la
reprise depuis un devis sans 3D) — il ne sera retiré que lorsque tous auront
leur remplaçant (lot 6, point c).
"""
from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def configure_product(self):
        """Ouvrir la configuration 3D de ce produit.

        ⚠️ **PAS de `force_create` ici, et c'est l'INVERSE de la route publique.**
        Sur la boutique, tous les visiteurs anonymes sont le même utilisateur :
        réutiliser une session donnerait au suivant la configuration du
        précédent. Au back-office, l'appelant est une personne identifiée, et
        `create_get_session` lui rend **sa** session brouillon pour ce produit :
        le commercial reprend là où il s'était arrêté. Même fonction, drapeau
        opposé, et les deux sont justes dans leur contexte.
        """
        self.ensure_one()
        session = self.env["product.config.session"].create_get_session(self.id)
        return session.action_open_3d_page()
