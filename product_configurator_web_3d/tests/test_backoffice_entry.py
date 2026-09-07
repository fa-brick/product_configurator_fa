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

    def test_la_cle_a_molette_ouvre_le_configurateur_EN_DIALOGUE(self):
        """⚠️ Amendé le 2026-09-07 : c'était un onglet, et un onglet fait perdre
        de vue ce qu'on faisait — *« une nouvelle page s'ouvre au lieu d'un
        dialogue comme pour une ligne de devis »* (Gerry). Une action CLIENTE en
        `target: "new"` : Odoo l'enveloppe lui-même."""
        action = self.tmpl.configure_product()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "product_configurator_web_3d.configurator")
        self.assertEqual(action["target"], "new")

    def test_le_dialogue_n_a_PAS_de_pied(self):
        """*« le Ok et donc le footer est inutile car la croix est présente »*
        (Gerry, 2026-09-07 — D-263).

        Odoo garnit d'office le pied d'une action cliente en dialogue d'un
        bouton « Ok » qui ne fait que fermer, comme la croix. Dans un
        configurateur, ce bouton-là se lit comme une validation qu'il n'est
        pas — la validation s'appelle « Confirmer » et vit dans le panneau.
        """
        action = self.tmpl.configure_product()
        self.assertFalse(action["context"]["footer"])

    def test_l_ETAT_part_avec_l_action_pour_eviter_un_aller_retour(self):
        """ⓘ Le serveur vient de le calculer ; le redemander au montage ferait
        attendre la page devant un écran vide (D-249)."""
        action = self.tmpl.configure_product()
        self.assertIn("state", action["params"])
        self.assertEqual(
            action["params"]["state"]["productName"], self.tmpl.display_name)

    def test_l_action_porte_le_JETON_et_jamais_l_identifiant(self):
        action = self.tmpl.configure_product()
        session = self.env["product.config.session"].search(
            [("product_tmpl_id", "=", self.tmpl.id)], order="id desc", limit=1
        )
        self.assertEqual(action["params"]["token"], session.access_token)
        self.assertNotIn("id", action["params"])

    def test_le_commercial_RETROUVE_sa_session(self):
        """⚠️ L'INVERSE de la route publique, et c'est voulu.

        Sur la boutique, `force_create=True` est obligatoire — tous les
        anonymes sont le même utilisateur. Ici l'appelant est identifié : sa
        session brouillon lui revient, et il reprend où il s'était arrêté.
        """
        premier = self.tmpl.configure_product()["params"]["token"]
        second = self.tmpl.configure_product()["params"]["token"]
        self.assertEqual(premier, second)
        self.assertEqual(len(self.env["product.config.session"].search(
            [("product_tmpl_id", "=", self.tmpl.id)])), 1)
