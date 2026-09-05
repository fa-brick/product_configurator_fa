# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""LA MAIN — un seul qui conduit, tous qui voient (D-255).

D-253 a ouvert le partage : deux personnes peuvent modifier la même
configuration. La main ne le REFERME pas — elle dit **qui conduit**, pour que
l'autre ne clique pas dans le dos du premier, et elle se prend d'un geste
explicite.

─ Ce que la main n'est PAS ─────────────────────────────────────────────────

⚠️ **Ce n'est pas un verrou de sécurité.** N'importe qui peut la prendre, et
c'est voulu : Gerry a tranché que l'interne agit sur la configuration du client
(D-253). Ce qui protège une session reste son JETON. La main empêche les
gestes qui se marchent dessus, pas les gestes qu'on n'a pas le droit de faire.

⓵ Elle se prend **implicitement** au premier geste, si personne ne l'a.
⓶ Elle se reprend **explicitement**, toujours, par un bouton — et l'autre le voit.
⓷ Elle se libère **toute seule** après un temps d'inactivité : un onglet fermé
   ne doit pas garder la main pour toujours, et personne ne pense à la rendre.
"""
from odoo import _, fields, models

# Inactivité au bout de laquelle la main retombe. Deux minutes : assez long pour
# réfléchir devant un produit, assez court pour qu'un onglet fermé ne bloque pas
# le suivant. ⚠️ Le compteur repart à CHAQUE geste, pas au premier.
HAND_TTL_SECONDS = 120


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    # ⚠️ `copy=False` : dupliquer une configuration ne duplique pas qui la tenait.
    hand_holder = fields.Char(
        string="Hand holder", copy=False,
        help="Opaque id of the page currently driving this configuration.",
    )
    hand_label = fields.Char(string="Hand label", copy=False)
    hand_since = fields.Datetime(string="Hand taken at", copy=False)

    def _hand_is_free(self):
        """Personne ne conduit — ou celui qui conduisait s'est absenté."""
        self.ensure_one()
        if not self.hand_holder or not self.hand_since:
            return True
        idle = (fields.Datetime.now() - self.hand_since).total_seconds()
        return idle > HAND_TTL_SECONDS

    def _hand_belongs_to(self, holder):
        self.ensure_one()
        return bool(holder) and self.hand_holder == holder

    def _take_hand(self, holder):
        """Prendre la main, et repartir le compteur d'inactivité.

        ⓘ Le LIBELLÉ vient du serveur, jamais du client : une page qui
        annoncerait elle-même son nom pourrait annoncer celui d'un autre. Pour
        un visiteur anonyme il n'y a pas de nom à donner — il y a un rôle.
        """
        self.ensure_one()
        label = self.env.user.name
        if self.env.user._is_public():
            label = _("Client")
        self.sudo().write({
            "hand_holder": holder,
            "hand_label": label,
            "hand_since": fields.Datetime.now(),
        })
        return True

    def _hand_state(self):
        """Ce que la page doit savoir de la main — et rien de plus.

        ⚠️ L'identifiant du porteur CIRCULE, et ce n'est pas une fuite : c'est
        un jeton de COORDINATION, pas un secret. Chaque page compare celui
        qu'elle reçoit au sien pour savoir si elle conduit. Le secret de cette
        configuration est son jeton d'accès, qui, lui, ne sort jamais.
        """
        self.ensure_one()
        if self._hand_is_free():
            return {"holder": None, "label": None}
        return {"holder": self.hand_holder, "label": self.hand_label}
