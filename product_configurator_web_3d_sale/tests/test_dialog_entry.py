# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Le devis ouvre le MÊME configurateur que le web — D-259, arbitré 2026-09-06.

Gerry : *« la mécanique est d'ajouter un produit en ligne et si ce produit est
configurable on ouvre le configurateur »*, en dialogue, sans quitter le devis.
Le but tenu ici est le SIEN : ne rien dupliquer, pour que ce qu'on change côté
client se voie au back-office le jour même.

⚠️ Ce qui se joue au serveur est éprouvé ici ; ce qui se joue à l'écran — le
dialogue, la scène, les formes — ne se prouve qu'en capture ([[L-215]]).
"""
from lxml import etree

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDialogEntry(TransactionCase):

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
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id,
                "value_ids": [Command.set((cls.blanc | cls.noir).ids)],
            })],
        })
        cls.ordinaire = cls.env["product.template"].create({"name": "Poignée"})

    # ── CE QUE LE CLIENT DOIT SAVOIR ─────────────────────────────────────

    def test_le_drapeau_suit_le_MODELE_pas_la_variante(self):
        """⚠️ Le cœur du piège : `config_ok` de la ligne suit `product_id`, et un
        produit configurable n'a pas encore de variante quand on le choisit."""
        line = self.env["sale.order.line"].new({
            "product_template_id": self.tmpl.id,
        })
        self.assertTrue(line.product_tmpl_config_ok)
        self.assertFalse(line.config_ok, "la variante n'existe pas encore")

    def test_un_produit_ORDINAIRE_ne_le_porte_pas(self):
        line = self.env["sale.order.line"].new({
            "product_template_id": self.ordinaire.id,
        })
        self.assertFalse(line.product_tmpl_config_ok)

    def test_le_champ_est_DANS_la_vue_sinon_il_n_arrive_jamais(self):
        """⚠️ Un champ absent de l'arch n'est pas chargé : le correctif
        retomberait en silence sur le dialogue d'Odoo."""
        arch = self.env["sale.order"].get_view(
            self.env.ref("sale.view_order_form").id, "form"
        )["arch"]
        champs = etree.fromstring(arch).xpath(
            "//field[@name='order_line']//field[@name='product_tmpl_config_ok']"
        )
        self.assertTrue(champs, "le drapeau ne parvient pas au client")

    # ── CE QUE LE DIALOGUE REÇOIT ────────────────────────────────────────

    def test_ouvrir_rend_JETON_et_ETAT_comme_la_page(self):
        opened = self.tmpl.web3d_open_configuration()
        self.assertTrue(opened["token"])
        self.assertTrue(opened["sessionId"])
        # C'est l'état de la PAGE, pas un format à part — sinon deux lectures.
        self.assertEqual(opened["state"]["productName"], self.tmpl.display_name)
        self.assertTrue(opened["state"]["attributes"])

    def test_ouvrir_DEUX_fois_ne_partage_pas_la_configuration(self):
        """⚠️ Deux lignes du même produit sont deux configurations. Réutiliser un
        brouillon en attacherait une à la mauvaise ligne."""
        a = self.tmpl.web3d_open_configuration()
        b = self.tmpl.web3d_open_configuration()
        self.assertNotEqual(a["sessionId"], b["sessionId"])

    def test_rouvrir_une_session_MONTRE_ce_qui_a_ete_repondu(self):
        first = self.tmpl.web3d_open_configuration()
        session = self.env["product.config.session"].browse(first["sessionId"])
        session.value_ids = [(6, 0, self.noir.ids)]
        again = self.tmpl.web3d_open_configuration(session_id=session.id)
        self.assertEqual(again["sessionId"], session.id)
        retenues = [
            v["name"] for a in again["state"]["attributes"]
            for v in a["values"] if v["chosen"]
        ]
        self.assertEqual(retenues, ["Noir"])

    # ── CE QUI DEVIENT OBSOLÈTE ──────────────────────────────────────────

    def test_les_deux_boutons_OCA_ne_s_affichent_PLUS(self):
        """Arbitré par Gerry : *« le bouton actuel de OCA ainsi que la
        fonctionnalité derrière devient obsolète »*. Masqués, pas supprimés —
        ils sont dans un module amont."""
        arch = etree.fromstring(self.env["sale.order"].get_view(
            self.env.ref("sale.view_order_form").id, "form"
        )["arch"])
        for nom in ("action_config_start", "reconfigure_product"):
            boutons = arch.xpath("//button[@name='%s']" % nom)
            self.assertTrue(boutons, "le bouton %s a disparu de la vue" % nom)
            self.assertEqual(
                boutons[0].get("invisible"), "1",
                "%s s'affiche encore et double le nouveau chemin" % nom,
            )
