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
        # ⓘ `variant` : la configuration NEUVE part des réponses de cette variante (liste de souhaits, D-557).
        variant = self._variant_of(product_tmpl, kwargs.get("variant"))
        if variant:
            session.value_ids = [(6, 0, variant.product_template_attribute_value_ids
                                  .product_attribute_value_id.ids)]
        session._ensure_access_token()
        # Le jeton entre dans l'URL — c'est la SEULE identité de ce visiteur.
        return request.redirect(f"/configurator/{session.access_token}")

    @staticmethod
    def _variant_of(product_tmpl, variant_id):
        """La variante demandée, si elle est bien une variante active de CE produit ; sinon rien.

        ⚠️ Jamais la configuration qui a fait naître la variante : elle appartient à un autre client (D-557).
        ⚠️ Une variante d'un autre produit est ignorée : ses réponses ne sont pas des questions de celui-ci (D-557).
        """
        try:
            variant_id = int(variant_id or 0)
        except ValueError:
            return None
        variant = request.env["product.product"].sudo().browse(variant_id).exists()
        if not variant or not variant.active or variant.product_tmpl_id != product_tmpl.sudo():
            return None
        return variant

    @http.route(
        "/configurator/optional_products", type="json", auth="public", website=True,
        methods=["POST"],
    )
    def optional_products(self, token=None, **kwargs):
        """Les optionnels du produit de cette configuration, prêts pour la fenêtre — D-537.

        ⚠️ Le jeton seul ouvre la session (`sudo`), comme sur les routes de `web_3d` ; les
        optionnels, eux, se lisent avec les droits du VISITEUR : il ne voit que ce qu'il peut acheter.
        """
        session = request.env["product.config.session"].sudo()._find_by_access_token(token)
        if not session:
            return []
        tmpl = request.env["product.template"].browse(session.product_tmpl_id.id)
        return tmpl._web_optional_products(request.website)
