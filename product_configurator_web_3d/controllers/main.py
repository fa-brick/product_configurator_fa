# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Les routes PUBLIQUES de la configuration — blocage n° 3 du lot 6.

⚠️ **Pourquoi elles existent.** Les quatre routes d'Odoo
(`/sale/product_configurator/*`) sont en `auth='user'` : le visiteur anonyme de
**D-091** — celui à qui l'on donne un jeton pour revenir sur sa configuration —
**ne peut pas les appeler**. Le montage « depuis un devis » fonctionne ; le
montage « depuis le site » n'avait aucune porte d'entrée. Les voici.

─ Le JETON est l'identité, et rien d'autre ──────────────────────────────────

D-091 : *« lors d'une configuration web, le visiteur a un code qui lui permet de
revenir sur sa configuration »*. Sur ces routes, il n'y a **pas d'utilisateur à
contrôler** — l'appelant est l'utilisateur *public*. Ce qui protège est le jeton :
32 octets aléatoires, jamais le numéro de session, qui est une **séquence
énumérable** (`CS0001`).

⚠️ **Trois refus, et ils se ressemblent volontairement.** Jeton absent, jeton
inconnu, jeton périmé : la réponse est la même, `unknown_session`. Distinguer
« inconnu » de « périmé » dirait à qui tâtonne quels jetons ont existé.

⚠️ **Et le jeton NE RESSORT PAS.** La réponse porte l'état de la configuration,
jamais l'identifiant interne de la session ni un autre jeton : une page publique
ne doit rien laisser filtrer qui permette d'énumérer.
"""
import json

from odoo import http
from odoo.http import request


class ProductConfiguratorWeb3D(http.Controller):

    def _session(self, token):
        """La session que ce jeton désigne, ou un ensemble vide.

        ⚠️ `sudo` est **nécessaire et suffisant** : l'utilisateur public n'a aucun
        droit sur `product.config.session`, et lui en donner par une règle
        d'enregistrement ouvrirait la lecture à tout le monde. Le contrôle est le
        jeton, et il a lieu ici — en un seul endroit, que les deux routes
        traversent.
        """
        return request.env["product.config.session"].sudo()._find_by_access_token(token)

    @http.route(
        "/configurator/<string:token>", type="http", auth="public", website=False,
        sitemap=False,
    )
    def page(self, token, **kwargs):
        """La page NUE — viewer à gauche, questions à droite (Gerry, 2026-08-26).

        ⚠️ **Le jeton n'est pas vérifié ici, et c'est délibéré.** La page se rend, le
        composant appelle `/configurator/state`, et c'est cette réponse qui dit si le
        lien vaut quelque chose. Vérifier deux fois obligerait à répondre deux fois la
        même chose — et un 404 ici dirait à qui tâtonne **quels jetons existent**, ce
        que D-190 refuse précisément.

        ⓘ `sitemap=False` : une configuration n'est pas une page à indexer. Sans lui,
        un moteur qui suivrait un lien partagé enregistrerait le jeton d'un client.
        """
        return request.render(
            "product_configurator_web_3d.configurator_page",
            {"props": json.dumps({"token": token})},
        )

    @http.route(
        "/configurator/state", type="json", auth="public", methods=["POST"],
        website=False, csrf=False,
    )
    def state(self, token=None, **kwargs):
        """L'état complet d'une configuration, en un aller-retour."""
        session = self._session(token)
        if not session:
            return {"error": "unknown_session"}
        return session.web_state()

    @http.route(
        "/configurator/set_value", type="json", auth="public", methods=["POST"],
        website=False, csrf=False,
    )
    def set_value(self, token=None, attribute_id=None, value_id=None, **kwargs):
        """Répondre à une question, et recevoir l'état qui en découle.

        ⚠️ **AUCUNE FOURCHE ICI, et c'est une décision** (D-190). `_session_for_edit`
        duplique une session quand l'utilisateur courant n'est pas son
        propriétaire — c'est le geste juste au **back-office**, où un commercial
        reprend la configuration d'un autre. Sur une route publique, l'appelant est
        toujours l'utilisateur *public* : forker à chaque clic créerait une session
        par réponse, et le visiteur perdrait la sienne au premier changement.
        **Le porteur du jeton EST le propriétaire.**

        ⚠️ Une session **confirmée** ne se modifie plus : elle a donné sa variante,
        et la changer sous une commande déjà passée serait pire qu'un refus.
        """
        session = self._session(token)
        if not session:
            return {"error": "unknown_session"}
        if session.state != "draft":
            return {"error": "session_closed"}
        value = request.env["product.attribute.value"].sudo().browse(int(value_id or 0))
        if not value.exists() or value.attribute_id.id != int(attribute_id or 0):
            # Une valeur qui n'appartient pas à la question posée n'est pas une
            # réponse : la retenir écrirait une configuration que rien ne relit.
            return {"error": "unknown_value"}
        # La réponse REMPLACE celle de la même question — une question à réponse
        # unique n'en garde qu'une, et c'est le cas de tout ce que la page montre
        # aujourd'hui.
        others = session.value_ids.filtered(
            lambda v, a=value.attribute_id: v.attribute_id != a
        )
        session.write({"value_ids": [(6, 0, (others | value).ids)]})
        return session.web_state()
