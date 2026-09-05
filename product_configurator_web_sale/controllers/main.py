# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La porte d'entrée depuis la BOUTIQUE — « Configurer » au lieu de « Ajouter au panier ».

Un produit configurable n'a pas de prix tant qu'il n'est pas configuré : le mettre
au panier d'un clic n'a donc pas de sens, et c'est pour cela que le bouton change
de nature plutôt que de libellé.

─ Une session NEUVE à chaque clic, et ce n'est pas un oubli ────────────────────

⚠️ `create_get_session` REUTILISE la dernière session de l'utilisateur courant
(`get_session_search_domain` : `user_id = self.env.uid`, `state = draft`). Sur la
boutique publique, **tous les visiteurs anonymes sont le même utilisateur** — le
docstring de `_ensure_access_token` le dit déjà : *« toutes les sessions anonymes
appartiendraient au même user_id, le jeton EST l'identité »*. Réutiliser
donnerait au visiteur suivant la configuration du précédent : son produit, ses
dimensions, son prix. D'où `force_create=True`, qui n'est pas une précaution mais
la seule forme juste ici (D-091, D-190).

ⓘ Le prix de ce choix est connu : un clic = une session. Les sessions
abandonnées sont déjà ramassées par l'`@api.autovacuum` du cœur.
"""
from odoo import http
from odoo.http import request


class ProductConfiguratorShopEntry(http.Controller):

    @http.route(
        ['/configurator/start/<model("product.template"):product_tmpl>'],
        type="http", auth="public", website=True, sitemap=False, methods=["GET"],
    )
    def start(self, product_tmpl, **kwargs):
        """Ouvrir une configuration NEUVE pour ce produit, et y emmener le visiteur.

        ⚠️ Un produit qui n'est PAS configurable ne rend pas une erreur : il
        renvoie à sa fiche. Le jour où quelqu'un décoche la case, les liens déjà
        partagés — courriel, favori, page en cache — ramènent le client sur le
        produit plutôt que sur un 404 qu'il ne saurait pas lire.
        """
        if not product_tmpl.config_ok:
            return request.redirect(product_tmpl.website_url)
        # ⚠️ `sudo` est nécessaire et suffisant : l'utilisateur public n'a aucun
        # droit d'écriture sur `product.config.session`, et lui en donner
        # ouvrirait la lecture de toutes les configurations. Ce qui protège la
        # session est son jeton, comme sur les deux routes de `web_3d`.
        session = request.env["product.config.session"].sudo().create_get_session(
            product_tmpl.id, force_create=True,
        )
        session._ensure_access_token()
        # Le jeton entre dans l'URL — c'est la SEULE identité de ce visiteur.
        return request.redirect(f"/configurator/{session.access_token}")
