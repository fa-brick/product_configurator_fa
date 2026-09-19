# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Reconfigurer une VARIANTE ouvre la page 3D — 2026-09-19.

La fiche d'une variante configurable porte deux entrées vers la
reconfiguration : un bouton d'en-tête et la flèche circulaire de la ligne de
variantes. Toutes deux appelaient l'assistant OCA.

⚠️ **Le wizard est mort** (arbitrage Gerry, 2026-09-19). Ces deux boutons ne
changent ni de place ni d'icône — seulement de destination, exactement comme la
clé à molette de la fiche produit l'a fait avant eux. C'est la règle qu'on
s'est donnée : on ne retire pas un geste que les gens connaissent, on le fait
aboutir au bon endroit.
"""
from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def reconfigure_product(self):
        """Rouvrir la configuration DE CETTE VARIANTE.

        Deux cas, et ils ne se ressemblent pas :

        ⓵ **La variante est née d'une configuration** — on rouvre CELLE-LÀ,
        telle quelle. C'est le cas « reprendre », et il doit être aussi sûr
        qu'un lien qu'on rouvre.

        ⓶ **Elle n'en a pas** — variante créée à la main, ou configurée avant
        que les sessions ne soient conservées. On en ouvre une neuve, **garnie
        des valeurs de la variante**, pour que la page montre ce que la fiche
        annonce et non une configuration vierge.

        ⚠️ **`force_create=False` ici**, contrairement à la ligne de devis : une
        session de ligne lui appartient, celle-ci appartient au produit. Rendre
        au commercial SA session brouillon pour ce modèle est exactement ce
        qu'on veut — il reprend là où il s'était arrêté.
        """
        self.ensure_one()
        Session = self.env["product.config.session"]
        session = Session.search(
            [("product_id", "=", self.id), ("state", "=", "done")],
            order="id desc", limit=1,
        )
        if not session:
            session = Session.create_get_session(self.product_tmpl_id.id)
            # ⓘ Les réponses de la variante deviennent celles de la session : sans
            # elles, la page s'ouvrirait vierge sur un produit qui, lui, est configuré.
            valeurs = self.product_template_attribute_value_ids
            session.value_ids = [(6, 0, valeurs.product_attribute_value_id.ids)]
        return session.action_open_3d_page()
