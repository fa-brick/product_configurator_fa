"""Ce qu'exécute `product.template` (BLL, D-541).

Le CRAYON de la fiche produit (`configure_product`) ouvre la configuration 3D.

ⓘ Même bouton et même place que dans le cœur du fork : seule la destination change ; le
crayon est l'icône qu'Odoo emploie sur la cellule produit d'une ligne de devis.
ⓘ L'assistant OCA n'a plus aucune entrée d'interface (D-097).

Ouvrir le configurateur 3D depuis le BACK-OFFICE — D-259.

On choisit un produit ; s'il est configurable, c'est notre configurateur qui
s'ouvre, en dialogue, sans quitter l'écran où l'on est. Le même composant que la
page publique : une seule implémentation des formes de question, du moteur et de
la scène.

⚠️ Ne pas le ramener dans le module du DEVIS : l'ordre de fabrication l'appelle aussi, et
devrait sinon dépendre de la vente.
⚠️ Ne pas en faire une seconde copie pour la fabrication : deux copies divergeraient ([[L-073]]).
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

    def web3d_open_configuration(self, session_id=None, **options):
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

        ⓘ `options` va à `_web_on_open` de la session, AVANT l'état : un module qui ouvre la
        page pour une commande y pose ce qui la chiffre (D-537).
        """
        self.ensure_one()
        Session = self.env["product.config.session"]
        session = Session.browse(session_id).exists() if session_id else Session
        # ⓘ D-371 — une ligne de DEVIS se corrige : sa configuration, confirmée, se rouvre
        # tant que le devis n'est pas une commande.
        if session:
            session._web_reopen_if_open_quote()
        if not session:
            session = Session.create_get_session(self.id, force_create=True)
        session._ensure_access_token()
        session._web_on_open(**options)
        return {
            "sessionId": session.id,
            "token": session.access_token,
            "state": session.web_state(),
        }
