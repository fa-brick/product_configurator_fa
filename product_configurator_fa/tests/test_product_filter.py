"""La liste PROPOSÉE par un filtre — C2, D-207.

⚠️ *« Un filtre sur des produits, uniquement »* (QI). Il ne fait que **proposer** :
ce que le client retient devient une valeur ordinaire (QJ), avec son prix et son
historique. La liste dynamique n'existe donc que pour les attributs de type
produit (QK) — les trois réponses se referment l'une l'autre.
"""

from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon


class ProductFilter(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.categorie = cls.env["product.category"].create({"name": "Handles C2"})
        cls.poignees = cls.env["product.product"].create([
            {"name": "Handle A", "categ_id": cls.categorie.id},
            {"name": "Handle B", "categ_id": cls.categorie.id},
        ])
        cls.autre = cls.env["product.product"].create({"name": "Not a handle"})
        cls.attribute = cls.env["product.attribute"].create({
            "name": "Handle C2", "create_variant": "no_variant",
            "value_type": "product",
        })

    def test_01_the_filter_PROPOSES_the_matching_products(self):
        self.attribute.product_filter_domain = str(
            [("categ_id", "=", self.categorie.id)]
        )
        proposes = self.attribute._proposed_products()
        self.assertEqual(proposes, self.poignees)
        self.assertNotIn(self.autre, proposes)

    def test_02_NO_filter_proposes_NOTHING(self):
        """⚠️ Et surtout pas le catalogue entier.

        Un attribut de type produit dont on n'a rien dit ne doit pas offrir tous
        les produits de la base — ce serait la pire des listes dynamiques.
        """
        self.assertFalse(self.attribute._proposed_products())

    def test_03_a_filter_only_makes_sense_on_a_PRODUCT_type(self):
        """Première barrière : ailleurs, il ne proposerait rien à personne."""
        plain = self.env["product.attribute"].create({
            "name": "Plain C2", "create_variant": "no_variant", "value_type": "value",
        })
        with self.assertRaises(ValidationError):
            plain.product_filter_domain = str([("categ_id", "=", self.categorie.id)])

    def test_04_an_UNAPPLICABLE_filter_is_refused_at_SAVE(self):
        """⚠️ Sinon il se découvre au moment de configurer — devant le client.

        Un domaine qui ne s'évalue pas ressemble alors à une panne, pas à une
        saisie. La garde l'éprouve en l'appliquant vraiment.
        """
        with self.assertRaises(ValidationError):
            self.attribute.product_filter_domain = str([("champ_inexistant", "=", 1)])

    def test_05_and_so_is_a_filter_that_is_not_even_a_domain(self):
        with self.assertRaises(ValidationError):
            self.attribute.product_filter_domain = "ceci n'est pas un domaine"

    def test_06_the_filter_only_PROPOSES_it_creates_nothing(self):
        """⚠️ Le cœur de QJ : rien n'est matérialisé tant que rien n'est choisi.

        Une liste dynamique qui créerait ses valeurs d'avance remplirait le
        catalogue de valeurs que personne n'a retenues.
        """
        self.attribute.product_filter_domain = str(
            [("categ_id", "=", self.categorie.id)]
        )
        self.attribute._proposed_products()
        self.assertFalse(self.attribute.value_ids)
