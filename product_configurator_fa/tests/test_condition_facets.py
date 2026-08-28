"""Une condition se lit comme une barre de recherche — B2, D-203.

⚠️ *« ET entre les pastilles, OU à l'intérieur d'une pastille. »* La sémantique
demandée par Gerry tombe juste sur le stockage existant ; ce résumé n'est qu'une
LECTURE, jamais un stockage — la condition reste faite d'enregistrements (D-080).
"""

from odoo.addons.base.tests.common import BaseCommon


class ConditionFacets(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.colour, cls.size = cls.env["product.attribute"].create([
            {"name": "Colour F", "create_variant": "no_variant"},
            {"name": "Size F", "create_variant": "no_variant"},
        ])
        cls.red, cls.blue = cls.env["product.attribute.value"].create([
            {"name": "Red", "attribute_id": cls.colour.id},
            {"name": "Blue", "attribute_id": cls.colour.id},
        ])
        cls.large = cls.env["product.attribute.value"].create(
            {"name": "Large", "attribute_id": cls.size.id}
        )
        cls.domain = cls.env["product.config.domain"].create({"name": "Rule F"})

    def _line(self, attribute, values, condition="in", operator="and", sequence=10):
        return self.env["product.config.domain.line"].create({
            "domain_id": self.domain.id,
            "attribute_id": attribute.id,
            "value_ids": [(6, 0, values.ids)],
            "condition": condition,
            "operator": operator,
            "sequence": sequence,
        })

    def test_01_no_rule_no_facet(self):
        """⚠️ Le cas le plus fréquent — la plupart des lignes ne portent rien."""
        self.assertFalse(self.domain.condition_summary)

    def test_02_one_rule_reads_as_ONE_facet(self):
        self._line(self.colour, self.red + self.blue)
        self.assertEqual(self.domain.condition_summary, "Colour F = Red / Blue")

    def test_03_OR_lives_INSIDE_a_facet(self):
        """Plusieurs valeurs dans une pastille : c'est le OU de la barre de recherche."""
        self._line(self.colour, self.red + self.blue)
        self.assertIn("Red / Blue", self.domain.condition_summary)
        self.assertNotIn(" or ", self.domain.condition_summary)

    def test_04_the_operator_governs_the_junction_with_the_NEXT_line(self):
        """⚠️ Contre-intuitif, et je l'avais écrit à l'envers.

        `to_odoo_domain` émet le `|` AVANT la ligne qui le porte, en notation
        préfixe : A en `or` donne `['|', A, B, C]`, soit **(A OU B) ET C**. Le
        lien annoncé devant la deuxième pastille est donc l'opérateur de la
        PREMIÈRE. Lu à l'envers, un `ou` s'afficherait sur la mauvaise jonction,
        et deux conditions différentes se liraient pareil.
        """
        self._line(self.colour, self.red, operator="or", sequence=10)
        self._line(self.size, self.large, operator="and", sequence=20)
        self.assertEqual(
            self.domain.condition_summary,
            "Colour F = Red • or Size F = Large",
        )

    def test_05_and_the_same_lines_with_AND_read_differently(self):
        """La garde précédente passerait si le lien était constant : celle-ci non."""
        self._line(self.colour, self.red, operator="and", sequence=10)
        self._line(self.size, self.large, operator="and", sequence=20)
        self.assertEqual(
            self.domain.condition_summary,
            "Colour F = Red • and Size F = Large",
        )

    def test_06_a_negative_rule_reads_as_NOT(self):
        self._line(self.colour, self.red, condition="not in")
        self.assertEqual(self.domain.condition_summary, "Colour F ≠ Red")

    def test_07_the_summary_FOLLOWS_the_rules(self):
        """C'est un calcul, pas une photo : changer une règle change le résumé."""
        line = self._line(self.colour, self.red)
        self.assertEqual(self.domain.condition_summary, "Colour F = Red")
        line.value_ids = self.blue
        self.assertEqual(self.domain.condition_summary, "Colour F = Blue")


class FacetsAreStructured(BaseCommon):
    """⚠️ **La pastille est STRUCTURÉE, pas une phrase** — constat de Gerry à

    l'écran : *« l'affichage de la condition ne reprend pas les étiquettes et la
    mécanique de celles du champ de recherche »*. Une facette du cœur a un
    segment d'entête, des valeurs séparées par un mot, et sa propre croix. Un
    unique texte ne peut pas rendre ça — il se lisait comme une ligne de tableau.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribut = cls.env["product.attribute"].create(
            {"name": "Facet mounting", "create_variant": "no_variant"}
        )
        cls.avant, cls.arriere = cls.env["product.attribute.value"].create([
            {"name": "Front", "attribute_id": cls.attribut.id},
            {"name": "Rear", "attribute_id": cls.attribut.id},
        ])
        cls.autre = cls.env["product.attribute"].create(
            {"name": "Facet finish", "create_variant": "no_variant"}
        )
        cls.mate = cls.env["product.attribute.value"].create(
            {"name": "Matt", "attribute_id": cls.autre.id}
        )

    def _condition(self, operateur="and", condition="in"):
        return self.env["product.config.domain"].create({
            "name": "Structured",
            "domain_line_ids": [
                (0, 0, {
                    "attribute_id": self.attribut.id,
                    "condition": condition,
                    "value_ids": [(6, 0, (self.avant | self.arriere).ids)],
                    "operator": operateur,
                    "sequence": 1,
                }),
                (0, 0, {
                    "attribute_id": self.autre.id,
                    "condition": "in",
                    "value_ids": [(6, 0, self.mate.ids)],
                    "sequence": 2,
                }),
            ],
        })

    def test_01_une_pastille_porte_son_ENTETE_et_ses_VALEURS_a_part(self):
        premiere = self._condition()._facet_data()[0]
        self.assertEqual(premiere["title"], "Facet mounting")
        self.assertEqual(premiere["values"], ["Front", "Rear"])
        self.assertFalse(premiere["negated"])

    def test_02_les_valeurs_d_une_MEME_pastille_se_lisent_en_OU(self):
        """D-203 : ET entre les pastilles, OU à l'intérieur d'une."""
        premiere = self._condition()._facet_data()[0]
        self.assertEqual(premiere["separator"], "or")

    def test_03_le_ET_entre_pastilles_est_IMPLICITE_comme_dans_la_barre(self):
        """Seul un « ou » se dit — sinon chaque condition s'alourdit d'un mot

        que la barre de recherche ne montre jamais.
        """
        facettes = self._condition(operateur="and")._facet_data()
        self.assertFalse(facettes[1]["link"])
        facettes = self._condition(operateur="or")._facet_data()
        self.assertEqual(facettes[1]["link"], "or")

    def test_04_et_la_NEGATION_se_dit_sur_la_pastille_qui_la_porte(self):
        premiere = self._condition(condition="not in")._facet_data()[0]
        self.assertTrue(premiere["negated"])

    def test_05_le_texte_plat_reste_rendu_pour_l_infobulle(self):
        """ⓘ Il sert d'infobulle et de lecture d'ordre — on ne le perd pas."""
        premiere = self._condition()._facet_data()[0]
        self.assertIn("Facet mounting", premiere["label"])
