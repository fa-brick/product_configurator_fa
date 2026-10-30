# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Le bouton de fin met-il au panier ? — D-553.

Ce qui est éprouvé : `cart` de `web_state`, que la page lit quand aucun hôte ne lui dit qu'elle
est dans la boutique — vrai sur le site, faux au back-office, faux pour une configuration qui a
déjà sa ligne de devis. Et le chemin réel : la page atteinte par `/configurator/start/`.
"""
from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestGoesToCart(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        attribute = cls.env["product.attribute"].create({"name": "Couleur D-553"})
        cls.white, cls.black = cls.env["product.attribute.value"].create([
            {"name": "Blanc", "attribute_id": attribute.id},
            {"name": "Noir", "attribute_id": attribute.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte D-553", "config_ok": True, "list_price": 100.0,
            "is_published": True, "sale_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": attribute.id,
                "value_ids": [Command.set((cls.white | cls.black).ids)],
            })],
        })
        cls.website = cls.env.ref("website.default_website")

    def _session(self):
        return self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
            "value_ids": [Command.set(self.white.ids)],
        })

    def _on_site(self, session):
        return session.with_context(cfg_on_site=True, website_id=self.website.id)

    def test_sur_le_site_la_confirmation_met_au_panier(self):
        self.assertTrue(self._on_site(self._session()).web_state()["cart"])

    def test_hors_du_site_la_confirmation_ne_fait_que_confirmer(self):
        self.assertFalse(self._session().web_state()["cart"])

    def test_une_configuration_qui_a_deja_sa_ligne_de_devis_ne_va_pas_au_panier(self):
        """⚠️ Sa ligne est mise à jour à la confirmation : un ajout au panier la doublerait."""
        session = self._session()
        session.action_confirm()
        self.env["sale.order"].create({
            "partner_id": self.env.user.partner_id.id,
            "order_line": [Command.create({"product_id": session.product_id.id,
                                           "config_session_id": session.id})],
        })
        self.assertFalse(self._on_site(session).web_state()["cart"])

    def test_la_page_atteinte_par_le_lien_de_la_boutique_met_au_panier(self):
        """Le chemin du défaut : le lien « Configurer » suivi sans l'overlay, puis l'état de la page."""
        # ⚠️ Suivre les redirections : la première est le 301 du produit vers son URL canonique, pas la configuration.
        response = self.url_open(f"/configurator/start/{self.tmpl.id}")
        token = response.url.rsplit("/configurator/", 1)[-1]
        on_site = self.make_jsonrpc_request("/configurator/state", {"token": token, "site": True})
        self.assertTrue(on_site["cart"])
        off_site = self.make_jsonrpc_request("/configurator/state", {"token": token})
        self.assertFalse(off_site["cart"])
