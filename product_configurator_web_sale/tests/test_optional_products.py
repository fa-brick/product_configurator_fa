# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Les produits optionnels d'un produit configuré, proposés après l'ajout au panier — D-537."""
from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class OptionalProducts(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Tmpl = cls.env["product.template"]
        cls.propellers = Tmpl.create({"name": "Hélices Omega", "list_price": 8.0,
                                      "is_published": True})
        cls.hidden = Tmpl.create({"name": "Sangle cachée", "list_price": 5.0,
                                  "is_published": False})
        cls.mount = Tmpl.create({"name": "Support configurable", "config_ok": True,
                                 "list_price": 12.0, "is_published": True})
        size = cls.env["product.attribute"].create({"name": "Taille Omega", "create_variant": "always"})
        small, large = cls.env["product.attribute.value"].create([
            {"name": "S Omega", "attribute_id": size.id},
            {"name": "L Omega", "attribute_id": size.id},
        ])
        cls.strap = Tmpl.create({
            "name": "Sangle à tailles", "list_price": 6.0, "is_published": True,
            "attribute_line_ids": [Command.create({"attribute_id": size.id,
                                                   "value_ids": [Command.set((small | large).ids)]})],
        })
        cls.frame = Tmpl.create({
            "name": "Châssis configurable", "config_ok": True, "list_price": 100.0,
            "is_published": True,
            "optional_product_ids": [Command.set(
                (cls.propellers | cls.hidden | cls.mount | cls.strap).ids)],
        })

    def _options(self):
        website = self.env["website"].get_current_website()
        return {o["name"]: o for o in self.frame._web_optional_products(website)}

    def test_un_optionnel_simple_s_ajoute_par_sa_variante(self):
        option = self._options()["Hélices Omega"]
        self.assertEqual(option["action"], "add")
        self.assertEqual(option["productId"], self.propellers.product_variant_id.id)

    def test_un_optionnel_non_publie_n_est_pas_propose(self):
        self.assertNotIn("Sangle cachée", self._options())

    def test_un_optionnel_configurable_se_configure(self):
        option = self._options()["Support configurable"]
        self.assertEqual(option["action"], "configure")
        self.assertTrue(option["url"].startswith("/configurator/start/"))
        self.assertTrue(option["fromPrice"])

    def test_un_optionnel_a_choix_s_ouvre_sur_sa_fiche(self):
        option = self._options()["Sangle à tailles"]
        self.assertEqual(option["action"], "view")
        self.assertEqual(option["url"], self.strap.website_url)

    def test_la_route_rend_les_optionnels_de_la_configuration(self):
        session = self.env["product.config.session"].create_get_session(
            self.frame.id, force_create=True)
        session._ensure_access_token()
        names = {o["name"] for o in self.make_jsonrpc_request(
            "/configurator/optional_products", {"token": session.access_token})}
        self.assertIn("Hélices Omega", names)
        self.assertNotIn("Sangle cachée", names)

    def test_un_jeton_inconnu_ne_rend_rien(self):
        self.assertEqual(self.make_jsonrpc_request(
            "/configurator/optional_products", {"token": "inconnu"}), [])
