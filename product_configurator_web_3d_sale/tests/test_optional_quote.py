# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Les produits optionnels proposés sur le devis après la fenêtre 3D — D-537."""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOptionalQuote(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Tmpl = cls.env["product.template"]
        cls.propellers = Tmpl.create({"name": "Hélices Sigma", "list_price": 10.0})
        cls.mount = Tmpl.create({"name": "Support Sigma", "config_ok": True, "list_price": 20.0})
        size = cls.env["product.attribute"].create({"name": "Taille Sigma", "create_variant": "always"})
        values = cls.env["product.attribute.value"].create([
            {"name": "S Sigma", "attribute_id": size.id}, {"name": "L Sigma", "attribute_id": size.id}])
        cls.strap = Tmpl.create({
            "name": "Sangle Sigma", "list_price": 6.0,
            "attribute_line_ids": [Command.create({"attribute_id": size.id,
                                                   "value_ids": [Command.set(values.ids)]})],
        })
        cls.frame = Tmpl.create({
            "name": "Châssis Sigma", "config_ok": True, "list_price": 100.0,
            "optional_product_ids": [Command.set((cls.propellers | cls.mount | cls.strap).ids)],
        })
        cls.pricelist = cls.env["product.pricelist"].create({
            "name": "Revendeur Sigma",
            "item_ids": [Command.create({"applied_on": "3_global", "compute_price": "percentage",
                                         "percent_price": 10})],
        })

    def _options(self, **kw):
        return {o["name"]: o for o in self.frame.web3d_optional_products(**kw)}

    def test_un_optionnel_simple_s_ajoute_par_sa_variante(self):
        option = self._options()["Hélices Sigma"]
        self.assertEqual(option["action"], "add")
        self.assertEqual(option["productId"], self.propellers.product_variant_id.id)

    def test_un_optionnel_configurable_se_configure(self):
        option = self._options()["Support Sigma"]
        self.assertEqual(option["action"], "configure")
        self.assertTrue(option["fromPrice"])

    def test_un_optionnel_a_choix_n_est_pas_propose(self):
        """⚠️ L'ajouter poserait une variante que personne n'a choisie."""
        self.assertNotIn("Sangle Sigma", self._options())

    def test_le_prix_suit_la_liste_du_devis(self):
        option = self._options(pricelist_id=self.pricelist.id,
                               date_order="2026-06-01 00:00:00")["Hélices Sigma"]
        self.assertIn("9", option["price"])
