# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La porte d'entrée depuis la boutique — le bouton, et ce qu'il ouvre.

Ce qui est éprouvé ici tient en trois questions : le bouton REMPLACE-t-il bien
celui du panier, la route rend-elle une configuration NEUVE, et deux visiteurs
anonymes reçoivent-ils bien deux configurations ? La dernière est la seule qui
ne se voit pas à l'écran, et c'est la plus grave si elle est fausse.
"""
from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestShopEntry(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.attribute = Attribute.create({"name": "Couleur"})
        cls.blanc, cls.noir = Value.create([
            {"name": "Blanc", "attribute_id": cls.attribute.id},
            {"name": "Noir", "attribute_id": cls.attribute.id},
        ])
        cls.configurable = cls.env["product.template"].create({
            "name": "Porte configurable",
            "config_ok": True,
            "list_price": 100.0,
            "is_published": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id,
                "value_ids": [Command.set((cls.blanc | cls.noir).ids)],
            })],
        })
        cls.ordinaire = cls.env["product.template"].create({
            "name": "Poignee simple",
            "list_price": 10.0,
            "is_published": True,
        })

    def _sessions_of(self, tmpl):
        return self.env["product.config.session"].sudo().search(
            [("product_tmpl_id", "=", tmpl.id)]
        )

    # ── LA FICHE PRODUIT ─────────────────────────────────────────────────

    def test_un_produit_configurable_se_configure_au_lieu_de_s_acheter(self):
        html = self.url_open(self.configurable.website_url).text
        self.assertIn("/configurator/start/", html)
        # ⚠️ C'est le REMPLACEMENT qu'on éprouve, pas l'ajout : laisser les deux
        # boutons côte à côte serait le vrai défaut, et il passerait inaperçu
        # dans un test qui ne chercherait que le nouveau.
        self.assertNotIn('id="add_to_cart"', html)

    def test_la_fiche_ne_dit_plus_que_la_combinaison_n_existe_pas(self):
        """⚠️ Sans variante, Odoo retombe sur son `t-else` et annonce une page
        vide de sens : *« This product has no valid combination »*. C'est l'état
        NORMAL d'un produit configurable avant sa premiere configuration."""
        html = self.url_open(self.configurable.website_url).text
        self.assertNotIn("no valid combination", html)

    def test_un_produit_ordinaire_ne_change_pas(self):
        html = self.url_open(self.ordinaire.website_url).text
        self.assertIn('id="add_to_cart"', html)
        self.assertNotIn("/configurator/start/", html)

    def test_la_vignette_de_la_grille_mene_a_la_configuration(self):
        html = self.url_open("/shop?search=Porte configurable").text
        self.assertIn("/configurator/start/", html)

    def test_pas_d_ajout_rapide_pour_ce_qui_doit_etre_configure(self):
        """Le verrou est en Python : la vue qui porte l'icône est optionnelle."""
        self.assertFalse(self.configurable._website_show_quick_add())
        self.assertTrue(self.ordinaire._website_show_quick_add())

    # ── LA ROUTE ─────────────────────────────────────────────────────────

    def test_la_route_ouvre_une_configuration_et_y_emmene(self):
        """⚠️ On SUIT les redirections, et il y en a deux.

        Odoo renvoie d'abord un 301 vers l'URL canonique du produit (le
        convertisseur `<model(...)>` normalise `65` en `porte-configurable-65`),
        puis notre route rend un 303 vers la configuration. Ne regarder que le
        premier code, c'est éprouver le convertisseur d'Odoo au lieu du module.
        """
        avant = self._sessions_of(self.configurable)
        response = self.url_open(f"/configurator/start/{self.configurable.id}")
        self.assertEqual(response.status_code, 200)
        session = self._sessions_of(self.configurable) - avant
        self.assertEqual(len(session), 1)
        self.assertTrue(session.access_token)
        self.assertEqual(session.state, "draft")
        # Le jeton — et LUI SEUL — est ce que l'URL porte.
        self.assertTrue(response.url.endswith(f"/configurator/{session.access_token}"))
        self.assertNotIn(f"/{session.id}", response.url)

    def test_deux_visiteurs_anonymes_ont_deux_configurations(self):
        """⚠️ LE test de ce module.

        Tous les visiteurs anonymes sont le MÊME utilisateur : sans
        `force_create`, `create_get_session` rendrait au second la configuration
        du premier — son produit, ses dimensions, son prix (D-091, D-190).
        """
        avant = self._sessions_of(self.configurable)
        premier = self.url_open(f"/configurator/start/{self.configurable.id}")
        second = self.url_open(f"/configurator/start/{self.configurable.id}")
        # ⚠️ Le CODE, et pas seulement l'URL : deux pages en erreur ont aussi
        # deux adresses différentes, et ce test-ci passait pendant que la page
        # d'arrivée rendait un 500.
        self.assertEqual([premier.status_code, second.status_code], [200, 200])
        self.assertEqual(len(self._sessions_of(self.configurable) - avant), 2)
        self.assertNotEqual(premier.url, second.url)

    def test_un_produit_non_configurable_revient_a_sa_fiche(self):
        """Décocher la case ne doit pas transformer les liens déjà partagés en 404."""
        avant = self._sessions_of(self.ordinaire)
        response = self.url_open(f"/configurator/start/{self.ordinaire.id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.url.endswith(self.ordinaire.website_url))
        self.assertEqual(self._sessions_of(self.ordinaire), avant)
