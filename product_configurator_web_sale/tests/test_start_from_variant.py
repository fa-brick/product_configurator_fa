# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Une configuration NEUVE préremplie des réponses d'une variante — D-557.

Ce qui est éprouvé : `/configurator/start/<produit>?variant=<id>` reprend les réponses de la variante,
dans une session neuve et non dans celle qui a fait naître la variante ; une variante d'un autre
produit, ou un identifiant illisible, laisse la configuration vierge.
"""
from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestStartFromVariant(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        color = Attribute.create({"name": "Couleur D-557", "value_ids": [
            Command.create({"name": "Blanc"}), Command.create({"name": "Noir"})]})
        cls.tmpl, cls.other = cls.env["product.template"].create([{
            "name": name, "config_ok": True, "list_price": 100.0, "is_published": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": color.id, "value_ids": [Command.set(color.value_ids.ids)]})],
        } for name in ("Porte D-557", "Fenêtre D-557")])
        cls.black = color.value_ids.filtered(lambda v: v.name == "Noir")
        # ⚠️ Les attributs neufs sont « Dynamique » : la variante naît de sa combinaison, pas d'avance (D-474).
        cls.variant = cls.tmpl._create_product_variant(
            cls.tmpl.attribute_line_ids.product_template_value_ids.filtered(lambda v: v.name == "Noir"))
        cls.foreign = cls.other._create_product_variant(
            cls.other.attribute_line_ids.product_template_value_ids.filtered(lambda v: v.name == "Noir"))

    def _started(self, variant_param):
        response = self.url_open(f"/configurator/start/{self.tmpl.id}?variant={variant_param}")
        token = response.url.rsplit("/configurator/", 1)[-1]
        return self.env["product.config.session"].sudo().search([("access_token", "=", token)])

    def test_la_configuration_part_des_reponses_de_la_variante(self):
        session = self._started(self.variant.id)
        self.assertEqual(session.value_ids, self.black)
        self.assertEqual(session.state, "draft")

    def test_jamais_la_configuration_qui_a_fait_naitre_la_variante(self):
        mine = self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
            "value_ids": [Command.set(self.black.ids)]})
        mine.action_confirm()
        self.assertNotEqual(self._started(mine.product_id.id), mine)

    def test_une_variante_d_un_autre_produit_est_ignoree(self):
        self.assertFalse(self._started(self.foreign.id).value_ids)

    def test_un_identifiant_illisible_est_ignore(self):
        self.assertFalse(self._started("abc").value_ids)
