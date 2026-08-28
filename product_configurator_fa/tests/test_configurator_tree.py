"""L'arbre du configurateur — la maquette de Gerry (D-210).

⚠️ Trois natures de lignes dans une seule liste : l'ÉTAPE en bandeau, l'ATTRIBUT,
et ses VALEURS indentées. Une liste Odoo ne sait ni s'imbriquer ni mêler deux
modèles — d'où un composant, et d'où cette structure rendue par le serveur.
"""

from odoo.addons.base.tests.common import BaseCommon


class ConfiguratorTree(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.step = cls.env["product.config.step"].create({"name": "Drone shape"})
        cls.kind = cls.env["product.attribute"].create(
            {"name": "Camplate kind", "create_variant": "no_variant"}
        )
        cls.classic, cls.cine = cls.env["product.attribute.value"].create([
            {"name": "Classic", "attribute_id": cls.kind.id},
            {"name": "Ciné", "attribute_id": cls.kind.id},
        ])
        cls.shape = cls.env["product.attribute"].create(
            {"name": "Shape", "create_variant": "no_variant"}
        )
        cls.round = cls.env["product.attribute.value"].create(
            {"name": "Round", "attribute_id": cls.shape.id}
        )
        cls.template = cls.env["product.template"].create({
            "name": "Cassette panel", "config_ok": True,
            "attribute_line_ids": [
                (0, 0, {"attribute_id": cls.kind.id,
                        "value_ids": [(6, 0, (cls.classic + cls.cine).ids)],
                        "sequence": 10}),
                (0, 0, {"attribute_id": cls.shape.id,
                        "value_ids": [(6, 0, cls.round.ids)],
                        "sequence": 20, "config_step_id": cls.step.id}),
            ],
        })

    def _rows(self):
        return self.template.get_configurator_tree()

    def test_01_an_attribute_carries_its_VALUES(self):
        rows = self._rows()
        attributs = [r for r in rows if r["kind"] == "attribute"]
        self.assertEqual([r["name"] for r in attributs], ["Camplate kind", "Shape"])
        self.assertEqual(
            [v["name"] for v in attributs[0]["values"]], ["Classic", "Ciné"]
        )

    def test_02_a_STEP_appears_as_its_own_row_before_what_it_opens(self):
        """⚠️ Le bandeau est DÉDUIT, pas stocké.

        Le modèle n'a pas changé (D-202) : l'étape reste un marqueur porté par la
        ligne qui l'ouvre. C'est l'affichage qui en tire un bandeau — ce que la
        forme (A) promettait.
        """
        rows = self._rows()
        genres = [r["kind"] for r in rows]
        self.assertEqual(genres, ["attribute", "step", "attribute"])
        self.assertEqual(rows[1]["name"], self.step.display_name)

    def test_03_the_rows_follow_the_ORDER_of_the_lines(self):
        """C'est l'ordre qui porte l'appartenance — le même que l'autre onglet."""
        self.template.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.shape
        ).sequence = 5
        rows = self._rows()
        self.assertEqual([r["kind"] for r in rows], ["step", "attribute", "attribute"])

    def test_04_a_condition_on_a_VALUE_reaches_its_row(self):
        """⚠️ Elle vit sur un AUTRE modèle — c'est la jointure que l'arbre fait.

        Sans elle, la maquette serait fausse : « Ciné » y porte une condition que
        « Classic » n'a pas, et les deux sont des valeurs du même attribut.
        """
        domaine = self.env["product.config.domain"].create({"name": "Only cine"})
        self.env["product.config.domain.line"].create({
            "domain_id": domaine.id, "attribute_id": self.shape.id,
            "value_ids": [(6, 0, self.round.ids)], "condition": "in",
            "operator": "and",
        })
        ligne = self.template.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.kind
        )
        self.env["product.config.line"].create({
            "product_tmpl_id": self.template.id,
            "attribute_line_id": ligne.id,
            "value_ids": [(6, 0, self.cine.ids)],
            "domain_id": domaine.id,
        })
        attributs = [r for r in self._rows() if r["kind"] == "attribute"]
        par_nom = {v["name"]: v for v in attributs[0]["values"]}
        self.assertTrue(par_nom["Ciné"]["facets"], "la condition de Ciné est perdue")
        self.assertFalse(par_nom["Classic"]["facets"], "Classic n'en porte aucune")

    def test_05_and_a_condition_on_the_ATTRIBUTE_reaches_its_own_row(self):
        domaine = self.env["product.config.domain"].create({"name": "Only round"})
        self.env["product.config.domain.line"].create({
            "domain_id": domaine.id, "attribute_id": self.shape.id,
            "value_ids": [(6, 0, self.round.ids)], "condition": "in",
            "operator": "and",
        })
        ligne = self.template.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.kind
        )
        ligne.visibility_domain_id = domaine
        attributs = [r for r in self._rows() if r["kind"] == "attribute"]
        self.assertTrue(attributs[0]["facets"])

    def test_06_the_3d_view_column_is_EMPTY_without_the_bridge(self):
        """ⓘ Le cœur ne connaît pas la caméra — il ne connaît qu'un crochet.

        ⚠️ Vide, et jamais `False` : la colonne l'afficherait tel quel.
        """
        attributs = [r for r in self._rows() if r["kind"] == "attribute"]
        self.assertIsInstance(attributs[0]["camera"], str)
