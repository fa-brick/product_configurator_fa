# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Le texte du bouton « Configurer », réglé dans les paramètres de la boutique — D-558.

Ce qui est éprouvé : vide, « Configure » traduit dans la langue du visiteur ; réglé, le texte de
chaque langue ; et ce texte sur la fiche produit et dans l'info-bulle de la grille, pages rendues.
"""
from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestConfigureButtonText(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        attribute = cls.env["product.attribute"].create({"name": "Couleur D-558", "value_ids": [
            Command.create({"name": "Blanc"}), Command.create({"name": "Noir"})]})
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte D-558", "config_ok": True, "list_price": 100.0,
            "is_published": True, "sale_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": attribute.id, "value_ids": [Command.set(attribute.value_ids.ids)]})],
        })
        cls.website = cls.env["website"].get_current_website()
        # ⚠️ Une langue inactive fait lever `env.lang` : la base de test n'a que l'anglais.
        cls.env["res.lang"]._activate_lang("fr_FR")
        # ⚠️ Une variante d'avance : sans elle, la fiche rend 500 en test, la liste de souhaits créant la
        # première variante pendant un GET en lecture seule — défaut connu, qu'Odoo rattrape hors test.
        cls.tmpl._create_product_variant(cls.tmpl.attribute_line_ids.product_template_value_ids[:1])

    def test_vide_le_bouton_dit_configure_dans_la_langue_du_visiteur(self):
        self.website.configure_button_text = False
        self.assertEqual(self.website._configure_button_label(), "Configure")
        self.assertEqual(self.website.with_context(lang="fr_FR")._configure_button_label(), "Configurer")

    def test_le_texte_regle_se_traduit_par_langue(self):
        self.website.configure_button_text = "Customize"
        self.website.with_context(lang="fr_FR").configure_button_text = "Personnaliser"
        self.assertEqual(self.website._configure_button_label(), "Customize")
        self.assertEqual(self.website.with_context(lang="fr_FR")._configure_button_label(), "Personnaliser")

    def test_les_parametres_ecrivent_la_langue_de_l_utilisateur_sans_bouton_de_langue(self):
        """⚠️ Le bouton de langue des paramètres ne ferait rien : la traduction passe par la fiche du site web."""
        field = self.env["res.config.settings"]._fields["website_configure_button_text"]
        self.assertFalse(field.translate)
        self.assertTrue(self.env["website"]._fields["configure_button_text"].translate)
        self.website.configure_button_text = "Customize"
        settings = self.env["res.config.settings"].with_context(lang="fr_FR").create({})
        settings.website_configure_button_text = "Personnaliser"
        settings.execute()
        self.assertEqual(self.website._configure_button_label(), "Customize")
        self.assertEqual(self.website.with_context(lang="fr_FR")._configure_button_label(), "Personnaliser")

    def test_la_fiche_produit_montre_le_texte_regle(self):
        self.website.configure_button_text = "Customize"
        html = self.url_open(self.tmpl.website_url).text
        self.assertRegex(html, r'o_cfg3d_configure"[^>]*>\s*<i class="fa fa-pencil me-2"></i>Customize\s*</a>')

    def test_l_info_bulle_de_la_grille_montre_le_texte_regle(self):
        self.website.configure_button_text = "Customize"
        self.website.with_context(website_id=self.website.id).viewref(
            "website_sale.products_add_to_cart").active = True
        html = self.url_open("/shop?search=Porte D-558").text
        self.assertIn('title="Customize"', html)
        self.assertIn('aria-label="Customize"', html)
