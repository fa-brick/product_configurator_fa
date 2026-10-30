# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La description d'une ligne configurée : le nom, puis une réponse par ligne — D-555.

Ce qui est éprouvé : la ligne de devis d'un article configuré, celle d'un article ordinaire à
variantes (inchangée), la description de vente gardée en dernier, et une question à une seule
valeur, qui n'est pas un choix et ne s'écrit pas.
"""
from odoo import Command

from odoo.addons.base.tests.common import BaseCommon


class TestLineDescription(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        cls.plate = Attribute.create({"name": "Plaque", "value_ids": [
            Command.create({"name": "Classic"}), Command.create({"name": "Light"})]})
        cls.color = Attribute.create({"name": "Couleur", "value_ids": [
            Command.create({"name": "Bleu"}), Command.create({"name": "Rouge"})]})
        cls.frame = Attribute.create({"name": "Cadre", "value_ids": [
            Command.create({"name": "Carbone"})]})
        cls.customer = cls.env["res.partner"].create({"name": "Client D-555"})

    def _template(self, config_ok, description=False):
        return self.env["product.template"].create({
            "name": "Drone D-555", "config_ok": config_ok, "description_sale": description,
            "attribute_line_ids": [
                Command.create({"attribute_id": a.id, "value_ids": [Command.set(a.value_ids.ids)]})
                for a in (self.plate, self.color, self.frame)
            ],
        })

    def _line(self, template):
        # ⚠️ Les attributs neufs sont « Dynamique » : la variante naît de sa combinaison, pas d'avance (D-474).
        combination = template.attribute_line_ids.product_template_value_ids.filtered(
            lambda ptav: ptav.name in ("Light", "Rouge", "Carbone"))
        variant = template._create_product_variant(combination)
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "order_line": [Command.create({"product_id": variant.id})],
        })
        return order.order_line

    def test_un_article_configure_ecrit_son_nom_puis_une_reponse_par_ligne(self):
        line = self._line(self._template(config_ok=True))
        self.assertEqual(line.name.splitlines(), ["Drone D-555", "Plaque: Light", "Couleur: Rouge"])

    def test_la_description_de_vente_vient_apres_les_reponses(self):
        line = self._line(self._template(config_ok=True, description="Livré monté."))
        self.assertEqual(line.name.splitlines()[-1], "Livré monté.")
        self.assertEqual(line.name.splitlines()[0], "Drone D-555")

    def test_un_article_ordinaire_garde_le_nom_de_variante_d_odoo(self):
        line = self._line(self._template(config_ok=False))
        self.assertEqual(line.name, "Drone D-555 (Light, Rouge)")
