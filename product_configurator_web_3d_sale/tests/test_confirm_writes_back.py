# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La configuration ATTERRIT sur la ligne de devis — la boucle se ferme.

Sans ce crochet, un commercial ouvrait la page depuis sa ligne, configurait, et
rien ne revenait : le prix suivait, mais la variante n'existait que dans la
session.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestConfirmWritesBack(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create({"name": "Couleur"})
        cls.blanc, cls.noir = cls.env["product.attribute.value"].create([
            {"name": "Blanc", "attribute_id": cls.attribute.id},
            {"name": "Noir", "attribute_id": cls.attribute.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte a terminer",
            "config_ok": True,
            "list_price": 100.0,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id,
                "value_ids": [Command.set((cls.blanc | cls.noir).ids)],
            })],
        })
        cls.partner = cls.env["res.partner"].create({"name": "Client d'essai"})

    def _configured_line(self, values):
        """Une ligne de devis avec sa session ouverte, comme après un clic sur
        la roue dentée."""
        session = self.env["product.config.session"].create_get_session(
            self.tmpl.id, force_create=True
        )
        session.value_ids = [(6, 0, values.ids)]
        variant = session.create_get_variant()
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": variant.id,
            "product_uom_qty": 1,
        })
        # La session qui SERVIRA à reconfigurer — neuve, attachée à la ligne.
        reprise = self.env["product.config.session"].create_get_session(
            self.tmpl.id, force_create=True
        )
        reprise.value_ids = [(6, 0, values.ids)]
        line.config_session_id = reprise
        return line, reprise

    def test_la_variante_confirmee_se_POSE_sur_la_ligne(self):
        line, session = self._configured_line(self.blanc)
        avant = line.product_id
        session.value_ids = [(6, 0, self.noir.ids)]
        session.web_confirm()
        self.assertEqual(session.state, "done")
        self.assertTrue(session.product_id)
        self.assertEqual(line.product_id, session.product_id)
        self.assertNotEqual(line.product_id, avant)

    def test_le_prix_de_la_ligne_suit_la_configuration(self):
        line, session = self._configured_line(self.blanc)
        session.web_confirm()
        self.assertEqual(line.price_unit, session.price)
        self.assertGreater(line.price_unit, 0.0)

    def test_un_devis_qui_n_est_PLUS_en_brouillon_ne_bouge_pas(self):
        """⚠️ Une commande confirmée porte des engagements — prix, délais,
        stock. Y changer un produit parce qu'un lien traînait dans une boîte
        mail serait un dégât, pas un service."""
        line, session = self._configured_line(self.blanc)
        intact = line.product_id
        line.order_id.sudo().write({"state": "sale"})
        session.value_ids = [(6, 0, self.noir.ids)]
        session.web_confirm()
        # La session, elle, va au bout : c'est la LIGNE qu'on protège.
        self.assertEqual(session.state, "done")
        self.assertEqual(line.product_id, intact)
