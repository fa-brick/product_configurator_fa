# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La CLÉ À MOLETTE de la fiche produit — arbitrage Gerry, 2026-09-05.

Le bouton existait déjà et ouvrait l'assistant OCA. Ce qui est éprouvé ici est
donc un CHANGEMENT de destination, et la propriété qui va avec : un commercial
qui rouvre son produit retrouve SA configuration, il n'en recommence pas une.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBackofficeEntry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create({"name": "Couleur"})
        cls.blanc = cls.env["product.attribute.value"].create(
            {"name": "Blanc", "attribute_id": cls.attribute.id}
        )
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte configurable",
            "config_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id,
                "value_ids": [Command.set(cls.blanc.ids)],
            })],
        })

    def test_la_cle_a_molette_ouvre_la_page_3d(self):
        action = self.tmpl.configure_product()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertTrue(action["url"].startswith("/configurator/"))
        # ⓘ Un onglet à côté : le commercial garde son devis derrière.
        self.assertEqual(action["target"], "new")

    def test_l_action_porte_le_JETON_et_jamais_l_identifiant(self):
        action = self.tmpl.configure_product()
        session = self.env["product.config.session"].search(
            [("product_tmpl_id", "=", self.tmpl.id)], order="id desc", limit=1
        )
        self.assertEqual(action["url"], f"/configurator/{session.access_token}")
        self.assertNotIn(session.name, action["url"])

    def test_le_commercial_RETROUVE_sa_session(self):
        """⚠️ L'INVERSE de la route publique, et c'est voulu.

        Sur la boutique, `force_create=True` est obligatoire — tous les
        anonymes sont le même utilisateur. Ici l'appelant est identifié : sa
        session brouillon lui revient, et il reprend où il s'était arrêté.
        """
        premier = self.tmpl.configure_product()["url"]
        second = self.tmpl.configure_product()["url"]
        self.assertEqual(premier, second)
        self.assertEqual(len(self.env["product.config.session"].search(
            [("product_tmpl_id", "=", self.tmpl.id)])), 1)
