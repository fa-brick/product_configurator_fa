"""LES CATÉGORIES DES RÉPONSES — les pastilles du panneau de choix (D-382, Gerry 2026-09-30).

Une réponse qui désigne une MATIÈRE se range sous la catégorie de celle-ci (un arbre depuis
D-382). Ce qui est éprouvé : la FEUILLE seule se nomme, le parent ne vient qu'entre deux
homonymes, l'ordre est celui de la séquence, et une réponse sans catégorie n'a aucune clé.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAnswerCategories(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Category = cls.env["product.model3d.material.category"]
        cls.bois = Category.create({"name": "Bois", "sequence": 1})
        cls.chene = Category.create({"name": "Chêne", "parent_id": cls.bois.id, "sequence": 2})
        cls.noyer = Category.create({"name": "Noyer", "parent_id": cls.bois.id, "sequence": 1})
        cls.chene_clair = Category.create({"name": "Clair", "parent_id": cls.chene.id, "sequence": 5})
        cls.noyer_clair = Category.create({"name": "Clair", "parent_id": cls.noyer.id, "sequence": 5})
        Material = cls.env["product.model3d.material"]
        materials = {
            "Chêne brut": cls.chene, "Noyer huilé": cls.noyer,
            "Chêne blanchi": cls.chene_clair, "Noyer pâle": cls.noyer_clair, "Sans famille": False,
        }
        cls.attribute = cls.env["product.attribute"].create({
            "name": "Essence", "create_variant": "no_variant", "value_type": "material",
            "display_type": "swatch", "answer_layout": "summary",
        })
        cls.values = {}
        for name, category in materials.items():
            material = Material.create({"name": name, "category_id": category and category.id})
            cls.values[name] = cls.env["product.attribute.value"].create({
                "name": name, "attribute_id": cls.attribute.id, "material_id": material.id})
        tmpl = cls.env["product.template"].create({
            "name": "Plateau configurable", "config_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id,
                "value_ids": [Command.set([v.id for v in cls.values.values()])],
            })],
        })
        cls.session = cls.env["product.config.session"].create(
            {"product_tmpl_id": tmpl.id, "user_id": cls.env.user.id})

    def _question(self):
        return self.session.web_state()["attributes"][0]

    def _keys(self, question):
        return {v["name"]: v["categoryKeys"] for v in question["values"]}

    def test_la_feuille_seule_se_nomme_dans_l_ordre_de_la_sequence(self):
        question = self._question()
        self.assertEqual([c["name"] for c in question["categories"]],
                         ["Noyer", "Chêne", "Clair (Chêne)", "Clair (Noyer)"])

    def test_chaque_reponse_porte_la_cle_de_sa_matiere_prefixee(self):
        keys = self._keys(self._question())
        self.assertEqual(keys["Chêne brut"], ["m%s" % self.chene.id])
        self.assertEqual(keys["Noyer pâle"], ["m%s" % self.noyer_clair.id])
        # ⓘ Sans catégorie : aucune clé — la page la range sous « Autres ».
        self.assertEqual(keys["Sans famille"], [])

    def test_une_seule_feuille_de_ce_nom_ne_prend_pas_de_parent(self):
        # ⓘ Directement sur un sous-ensemble : une valeur employée par un produit ne se
        # supprime pas, et c'est la question MONTRÉE qui compte.
        shown = self.env["product.attribute.value"].union(
            *(v for name, v in self.values.items() if name != "Noyer pâle"))
        categories, _keys = self.session._web_categorized(shown)
        names = [c["name"] for c in categories]
        self.assertIn("Clair", names)
        self.assertNotIn("Clair (Chêne)", names)
