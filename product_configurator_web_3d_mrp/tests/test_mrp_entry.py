# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""L'ordre de fabrication ouvre le MÊME configurateur que le devis — 2026-09-19.

Gerry : *« lorsque l'on clique sur nouveau et que l'on sélectionne un produit
configuré, que cela déclenche le configurateur comme lors d'un devis — cela
évite la présence inutile de ce bouton »*, et : *« pour moi le wizard est
mort. »*

⚠️ Ce qui se joue à l'ÉCRAN — la liste déroulante augmentée, le dialogue, la
scène — ne se prouve qu'en capture ([[L-215]]). Ce banc tient ce qui se prouve
au serveur : que le wizard a bien disparu, que rien ne le rappelle, et que la
vue pose le widget là où il faut.
"""
from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMrpEntry(TransactionCase):

    # ── LE WIZARD EST MORT ───────────────────────────────────────────────

    def test_le_modele_du_wizard_n_existe_PLUS(self):
        """⚠️ Arbitré : *« pour moi le wizard est mort, on peut le supprimer. »*

        Le modèle était celui de l'assistant OCA, ouvert par un bouton injecté
        dans toutes les listes du back-office. Le configurateur 3D le remplace.
        """
        self.assertNotIn("product.configurator.mrp", self.env)

    def test_les_DEUX_methodes_qui_l_ouvraient_ont_disparu(self):
        """Elles n'existaient que pour lui : `action_config_start` depuis le
        bouton de liste, `reconfigure_product` depuis le formulaire."""
        production = self.env["mrp.production"]
        for nom in ("action_config_start", "reconfigure_product"):
            self.assertFalse(hasattr(production, nom),
                             "`%s` survit au wizard qu'elle ouvrait" % nom)

    def test_le_bouton_Reconfigure_a_quitte_la_vue(self):
        """Il ouvrait le wizard, et lui seul."""
        arch = etree.fromstring(self.env["mrp.production"].get_view(
            self.env.ref("mrp.mrp_production_form_view").id, "form")["arch"])
        self.assertFalse(arch.xpath("//button[@name='reconfigure_product']"))

    # ── CE QUI LE REMPLACE ───────────────────────────────────────────────

    def test_le_champ_produit_porte_NOTRE_widget(self):
        """⚠️ C'est la seule accroche, et elle est CADRÉE : un widget nommé dans
        la vue ne s'exécute que là où on l'a posé.

        Le bouton supprimé faisait l'inverse — il s'injectait dans les gabarits
        génériques de toutes les listes, kanbans et formulaires, se cachait en
        CSS, puis se rallumait en JS quand le modèle était le bon.
        """
        arch = etree.fromstring(self.env["mrp.production"].get_view(
            self.env.ref("mrp.mrp_production_form_view").id, "form")["arch"])
        champs = arch.xpath("//field[@name='product_id']")
        self.assertTrue(champs, "le champ produit a disparu de la vue")
        self.assertEqual(champs[0].get("widget"), "mrp_config_product")

    def test_la_SESSION_voyage_avec_la_fiche(self):
        """⚠️ Sans elle, rouvrir une configuration partirait d'une page NEUVE, et
        la session déjà liée à l'ordre serait remplacée sans un mot."""
        arch = etree.fromstring(self.env["mrp.production"].get_view(
            self.env.ref("mrp.mrp_production_form_view").id, "form")["arch"])
        self.assertTrue(arch.xpath("//field[@name='config_session_id']"))

    def test_le_lien_vers_la_configuration_SURVIT_au_wizard(self):
        """ⓘ Ce n'est pas lui qui meurt : le configurateur 3D l'écrit comme le
        faisait l'assistant, et c'est par lui que l'ordre retrouve ses réponses."""
        self.assertIn("config_session_id", self.env["mrp.production"]._fields)

    # ── LA PRÉPARATION EST PARTAGÉE AVEC LE DEVIS ────────────────────────

    def test_la_preparation_est_celle_du_DEVIS(self):
        """⚠️ Une seconde préparation aurait divergé de la première ([[L-073]]).
        Elle a donc quitté le module du devis pour celui qui possède la PAGE."""
        self.assertTrue(hasattr(self.env["product.template"],
                                "web3d_open_configuration"))
