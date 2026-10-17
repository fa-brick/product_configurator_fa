# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Le CRAYON de la fiche produit (`configure_product`) ouvre la configuration 3D.

ⓘ Même bouton et même place que dans le cœur du fork : seule la destination change ; le
crayon est l'icône qu'Odoo emploie sur la cellule produit d'une ligne de devis.
ⓘ L'assistant OCA n'a plus aucune entrée d'interface (D-097).
"""
from odoo import models
from odoo.exceptions import UserError


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

    def _configurator_camera_choices(self):
        """Le crochet du cœur, rempli ici : les vues des modèles 3D de ce produit (D-386).

        ⓘ Le même domaine que `view_camera_id` : la liste de l'arbre ne propose que ce
        que le formulaire accepterait.
        """
        self.ensure_one()
        cameras = self.env["product.model3d.camera"].search(
            [("model3d_id.product_tmpl_id", "=", self.id)], order="name, id")
        return [{"id": camera.id, "name": camera.display_name} for camera in cameras]

    def _configurator_camera_of(self, camera_id):
        """La vue désignée — REFUSÉE si elle n'est pas une vue de ce produit."""
        self.ensure_one()
        if not camera_id:
            return self.env["product.model3d.camera"]
        if camera_id not in [choice["id"] for choice in self._configurator_camera_choices()]:
            raise UserError(self.env._("This 3D view does not belong to this product."))
        return self.env["product.model3d.camera"].browse(camera_id)
