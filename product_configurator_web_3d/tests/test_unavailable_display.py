# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Griser ou masquer une valeur indisponible — D-168, écrit par D-368.

Le cas de Gerry : le bumper avant du JeNo dépend de la Cam plate. En Classic, le
bumper Ciné ne s'offre pas ; masqué, le client ne le voit pas du tout.

⚠️ Ce qui est éprouvé est ce que la PAGE reçoit (`web_state`) : c'est là que le
filtre vit, pour que la liste déroulante et les suggestions en profitent aussi.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestUnavailableDisplay(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.plate = Attribute.create({"name": "Cam plate"})
        cls.classic, cls.cine_plate = Value.create([
            {"name": "Classic", "attribute_id": cls.plate.id},
            {"name": "Ciné", "attribute_id": cls.plate.id},
        ])
        cls.bumper = Attribute.create({"name": "Bumper avant"})
        cls.sans, cls.bumper_a, cls.bumper_cine = Value.create([
            {"name": "Sans bumper", "attribute_id": cls.bumper.id},
            {"name": "Classic A", "attribute_id": cls.bumper.id},
            {"name": "Bumper Ciné", "attribute_id": cls.bumper.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Drone configurable",
            "config_ok": True,
            "attribute_line_ids": [
                Command.create({
                    "attribute_id": cls.plate.id,
                    "value_ids": [Command.set((cls.classic | cls.cine_plate).ids)],
                }),
                Command.create({
                    "attribute_id": cls.bumper.id,
                    "value_ids": [Command.set(
                        (cls.sans | cls.bumper_a | cls.bumper_cine).ids)],
                }),
            ],
        })
        cls.bumper_line = cls.tmpl.attribute_line_ids.filtered(
            lambda line: line.attribute_id == cls.bumper)
        # Une règle par valeur (D-165 Q-1) : « Sans bumper » n'en a aucune, c'est le filet.
        Domain = cls.env["product.config.domain"]
        for value, plate in ((cls.bumper_a, cls.classic), (cls.bumper_cine, cls.cine_plate)):
            domain = Domain.create({
                "name": "Cam plate = %s" % plate.name,
                "domain_line_ids": [Command.create({
                    "attribute_id": cls.plate.id,
                    "condition": "in",
                    "value_ids": [Command.set(plate.ids)],
                    "operator": "and",
                })],
            })
            cls.env["product.config.line"].create({
                "product_tmpl_id": cls.tmpl.id,
                "attribute_line_id": cls.bumper_line.id,
                "value_ids": [Command.set(value.ids)],
                "domain_id": domain.id,
            })
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": cls.tmpl.id,
            "user_id": cls.env.user.id,
            "value_ids": [Command.set(cls.classic.ids)],
        })

    def _bumper_values(self):
        state = self.session.web_state()
        question = next(q for q in state["attributes"] if q["id"] == self.bumper.id)
        return {v["name"]: v["available"] for v in question["values"]}

    def test_par_défaut_la_valeur_indisponible_est_GRISÉE(self):
        """Ce que la page a toujours fait : montrée, éteinte."""
        self.assertEqual(self.bumper.unavailable_display, "grey")
        self.assertEqual(self._bumper_values(), {
            "Sans bumper": True, "Classic A": True, "Bumper Ciné": False,
        })

    def test_l_attribut_qui_MASQUE_retire_la_valeur_de_la_page(self):
        self.bumper.unavailable_display = "hide"
        self.assertEqual(self._bumper_values(), {"Sans bumper": True, "Classic A": True})

    def test_masquer_suit_la_réponse_changer_de_plaque_change_ce_qui_se_voit(self):
        self.bumper.unavailable_display = "hide"
        self.session.write({"value_ids": [Command.set(self.cine_plate.ids)]})
        self.assertEqual(self._bumper_values(), {"Sans bumper": True, "Bumper Ciné": True})

    def test_la_ligne_VIDE_hérite_de_l_attribut(self):
        """⚠️ Pas une semence : changer l'attribut change le produit qui n'a rien réglé."""
        self.assertFalse(self.bumper_line.unavailable_display)
        self.bumper.unavailable_display = "hide"
        self.assertEqual(self.bumper_line._unavailable_display(), "hide")

    def test_la_ligne_du_produit_SURCHARGE_l_attribut(self):
        """« Couleur masque partout, sauf sur le produit qui préfère griser » (D-168)."""
        self.bumper.unavailable_display = "hide"
        self.bumper_line.unavailable_display = "grey"
        self.assertIn("Bumper Ciné", self._bumper_values())
        self.bumper.unavailable_display = "grey"
        self.bumper_line.unavailable_display = "hide"
        self.assertNotIn("Bumper Ciné", self._bumper_values())

    def test_une_valeur_CHOISIE_reste_montrée_même_indisponible(self):
        """Le cas d'une pièce posée, dont la réponse n'est pas élaguée : une question
        répondue sans réponse visible serait pire que le grisé."""
        self.bumper.unavailable_display = "hide"
        Session = self.env["product.config.session"]
        values = self.sans | self.bumper_a | self.bumper_cine
        shown = Session._web_shown_values(
            self.bumper_line, values, {self.sans.id}, [self.bumper_cine.id])
        self.assertEqual(shown, self.sans | self.bumper_cine)
