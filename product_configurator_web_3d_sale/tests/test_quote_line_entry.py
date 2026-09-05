# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Configurer et REPRENDRE depuis une ligne de devis — arbitrage Gerry, 2026-09-05.

Deux cas qui ne se ressemblent pas, et un piège de prix entre les deux : lier
une session à une ligne fait recalculer le prix de cette ligne
(`_compute_price_unit` lit `config_session_id.price`). Une session vide mettrait
donc la ligne à zéro, sans un mot.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestQuoteLineEntry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create({"name": "Couleur"})
        cls.blanc, cls.noir = cls.env["product.attribute.value"].create([
            {"name": "Blanc", "attribute_id": cls.attribute.id},
            {"name": "Noir", "attribute_id": cls.attribute.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte configurable",
            "config_ok": True,
            "list_price": 100.0,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id,
                "value_ids": [Command.set((cls.blanc | cls.noir).ids)],
            })],
        })
        # ⚠️ Un produit configurable n'a AUCUNE variante (le fork ne les crée
        # qu'à la confirmation) : la seule façon d'en obtenir une, et donc
        # d'avoir une ligne de devis réaliste, est de configurer.
        cls.session_source = cls.env["product.config.session"].create_get_session(
            cls.tmpl.id, force_create=True
        )
        cls.session_source.value_ids = [(6, 0, cls.blanc.ids)]
        cls.variant = cls.session_source.create_get_variant()
        cls.partner = cls.env["res.partner"].create({"name": "Client d'essai"})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})

    def _line(self, session=None):
        return self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.variant.id,
            "product_uom_qty": 1,
            **({"config_session_id": session.id} if session else {}),
        })

    # ── ⓵ REPRENDRE ──────────────────────────────────────────────────────

    def test_une_ligne_qui_a_deja_sa_session_la_ROUVRE(self):
        line = self._line(session=self.session_source)
        action = line.reconfigure_product()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertEqual(
            action["url"], f"/configurator/{self.session_source.access_token}"
        )
        # ⚠️ Rouvrir ne doit RIEN changer : c'est un lien qu'on suit, pas un geste.
        self.assertEqual(line.config_session_id, self.session_source)

    # ── ⓶ CONFIGURER ─────────────────────────────────────────────────────

    def test_une_ligne_sans_session_en_recoit_une_ATTACHEE(self):
        line = self._line()
        self.assertFalse(line.config_session_id)
        action = line.reconfigure_product()
        self.assertTrue(line.config_session_id)
        self.assertEqual(
            action["url"], f"/configurator/{line.config_session_id.access_token}"
        )
        self.assertEqual(line.config_session_id.product_tmpl_id, self.tmpl)

    def test_la_session_neuve_est_PRE_REMPLIE_des_valeurs_de_la_variante(self):
        line = self._line()
        line.reconfigure_product()
        self.assertEqual(line.config_session_id.value_ids, self.blanc)

    def test_le_prix_de_la_ligne_ne_tombe_PAS_a_zero(self):
        """⚠️ Le vrai risque de ce module.

        `_compute_price_unit` recalcule à partir de `config_session_id.price`
        dès que le lien existe. Sans le pré-remplissage, ouvrir la
        configuration d'une ligne la mettrait à zéro — un devis faussé par un
        clic qui n'était censé qu'ouvrir une page.
        """
        line = self._line()
        line.reconfigure_product()
        self.assertGreater(line.price_unit, 0.0)
        self.assertEqual(line.price_unit, line.config_session_id.price)

    def test_deux_lignes_ne_PARTAGENT_pas_une_session(self):
        """⚠️ `force_create` ici, contrairement à la fiche produit : une session
        attachée à une ligne lui appartient."""
        premiere, seconde = self._line(), self._line()
        premiere.reconfigure_product()
        seconde.reconfigure_product()
        self.assertTrue(premiere.config_session_id)
        self.assertNotEqual(premiere.config_session_id, seconde.config_session_id)
