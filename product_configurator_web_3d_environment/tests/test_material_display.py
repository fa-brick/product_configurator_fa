# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""L'AFFICHAGE des listes de matières d'un environnement — celui d'un attribut (W-113, E-3c-3, D-451).

Ce qui est éprouvé : les formes proposées sont celles d'un attribut, sans les cases multiples ; la ligne d'un usage
porte son affichage, la disposition ramenée à ce que la forme permet ; l'onglet Infos le règle et refuse une valeur
inconnue ; les choix ne sortent qu'au back-office.
"""
from odoo.tests import TransactionCase, new_test_user, tagged


def square():
    nodes = [{"id": "n1", "x": 0, "y": 0}, {"id": "n2", "x": 4000, "y": 0},
             {"id": "n3", "x": 4000, "y": 4000}, {"id": "n4", "x": 0, "y": 4000}]
    walls = [{"id": "w%d" % i, "a": "n%d" % i, "b": "n%d" % (i % 4 + 1)} for i in range(1, 5)]
    return {"version": 1, "nodes": nodes, "walls": walls, "openings": []}


@tagged("post_install", "-at_install")
class TestMaterialDisplay(TransactionCase):

    def setUp(self):
        super().setUp()
        self.site = self.env["product.environment"].create({"name": "Chantier affichage", "plan": square()})
        self.employee = new_test_user(self.env, login="md_employee", groups="base.group_user")
        self.portal = new_test_user(self.env, login="md_portal", groups="base.group_portal")

    def rows(self, environment):
        return {row["use"]: row for row in environment.editor_state()["materialUses"]}

    def test_les_formes_d_un_attribut_sans_les_cases_multiples(self):
        Use = self.env["product.environment.material.use"]
        forms = {key for key, _label in Use._selection_display_type()}
        attribute = {key for key, _label in self.env["product.attribute"]._fields["display_type"]._description_selection(self.env)}
        self.assertEqual(forms, attribute - {"multi"})
        self.assertIn("swatch", forms)

    def test_la_ligne_porte_l_affichage_et_la_disposition_effective(self):
        floor = self.site.material_use_ids.filtered(lambda u: u.use == "floor")
        self.assertEqual(self.rows(self.site)["floor"]["displayType"], "swatch")
        floor.write({"display_type": "radio", "answer_layout": "line"})
        row = self.rows(self.site)["floor"]
        # ⓘ Une rangée « + Voir tout » ne vaut que pour les formes à image : la page reçoit la liste complète.
        self.assertEqual((row["answerLayout"], row["answerLayoutSet"]), ("inline", "line"))
        floor.display_type = "card"
        self.assertEqual(self.rows(self.site)["floor"]["answerLayout"], "line")

    def test_l_onglet_infos_regle_l_affichage(self):
        site = self.site.with_user(self.employee).sudo()
        result = site.editor_material_uses({"floor": {"displayType": "card", "answerSize": "large"}})
        self.assertTrue(result["ok"])
        floor = next(row for row in result["materialUses"] if row["use"] == "floor")
        self.assertEqual((floor["displayType"], floor["answerSize"]), ("card", "large"))
        self.assertEqual(site.editor_material_uses({"floor": {"displayType": "multi"}}), {"error": "invalid"})
        self.assertEqual(site.editor_material_uses({"floor": {"answerLayout": "spiral"}}), {"error": "invalid"})

    def test_les_choix_ne_sortent_qu_au_back_office(self):
        options = self.site.with_user(self.employee).sudo().editor_state()["materialDisplayOptions"]
        self.assertEqual(set(options), {"displayType", "swatchMark", "answerSize", "answerLayout"})
        self.assertNotIn("multi", [value for value, _label in options["displayType"]])
        self.assertNotIn("materialDisplayOptions", self.site.with_user(self.portal).sudo().editor_state())

    def test_l_affichage_part_avec_la_copie(self):
        template = self.env["product.environment"].create({"name": "Modèle affichage", "is_template": True,
                                                           "plan": square()})
        template.material_use_ids.filtered(lambda u: u.use == "interior").display_type = "pills"
        site = template.copy_for_site()
        self.assertEqual(site.material_use_ids.filtered(lambda u: u.use == "interior").display_type, "pills")
