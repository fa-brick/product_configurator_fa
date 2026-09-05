# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Qui a le droit d'ÉCOUTER une configuration — D-253.

Le canal d'une session est accordé à qui présente son **jeton**, exactement
comme la page l'est. C'est le même modèle d'accès de bout en bout : le jeton est
l'identité (D-091, D-190), et un interne qui ouvre la page d'un client l'ouvre
par ce même jeton.

ⓘ **Le précédent est celui du courrier** : `mail/models/discuss/ir_websocket.py`
accorde un canal à un visiteur anonyme qui présente `mail.guest_<jeton>`. On en
reprend la forme, mot pour mot.

⚠️ Odoo, dans SA propre édition collaborative (`web_editor/models/ir_websocket.py`),
refuse au contraire les utilisateurs publics. Nous faisons autrement parce que
le jeton nous le permet — mais cela veut dire que **quiconque tient le lien peut
regarder**, et c'est une posture à assumer, pas un oubli.
"""
from odoo import models

CHANNEL_PREFIX = "product.config.session_"


class IrWebsocket(models.AbstractModel):
    _inherit = "ir.websocket"

    def _build_bus_channel_list(self, channels):
        return super()._build_bus_channel_list(
            self._configurator_channel_list(channels)
        )

    def _configurator_channel_list(self, channels):
        """Remplacer chaque jeton par la session qu'il désigne.

        ⓘ **Séparé de `_build_bus_channel_list` pour être ÉPROUVABLE.** La
        chaîne complète des surcharges d'Odoo finit chez `mail`, qui lit le
        cookie de l'invité — donc exige une vraie requête HTTP. Ce qui doit être
        vérifié est ici ; ce qui reste au-dessus est une ligne de glu.
        """
        # ⚠️ Ne pas altérer la liste reçue : les autres modules la traversent
        # après nous (c'est la précaution que prend `mail`).
        channels = list(channels)
        for channel in list(channels):
            if not isinstance(channel, str) or not channel.startswith(CHANNEL_PREFIX):
                continue
            channels.remove(channel)
            token = channel[len(CHANNEL_PREFIX):]
            # ⓘ `_find_by_access_token` refuse déjà un jeton inconnu, périmé ou
            # archivé — et rend la MÊME chose dans les trois cas.
            session = self.env["product.config.session"].sudo()._find_by_access_token(
                token
            )
            if session:
                channels.append(session)
        return channels
