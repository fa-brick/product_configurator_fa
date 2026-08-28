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
            # ⓘ Le MODE, depuis D-218 : sans lui le filtre est inerte, et c'est
            # précisément ce que `test_11` éprouve.
            "dynamic_values": True,
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

    def test_06_posing_the_filter_MATERIALISES_what_it_proposes(self):
        """⚠️ **CE TEST DISAIT L'INVERSE, et c'est un changement de RÈGLE.**

        QJ posait : *« la valeur choisie est matérialisée »* — donc rien tant
        que rien n'est choisi, et ce test le tenait. Gerry a demandé ensuite
        d'*« afficher les enregistrements du filtre dans les valeurs
        d'attribut »* : la liste doit montrer ce que le filtre propose, sans
        attendre qu'un client passe.

        ⚠️ **Ce que la nouvelle règle coûte** : le catalogue porte désormais une
        valeur par produit proposé, retenue ou non. ⓘ `configurator_generated`
        les marque, et le ménage existant archive celles que plus rien n'emploie
        — une valeur jamais retenue finit donc par s'effacer d'elle-même.
        """
        self.attribute.product_filter_domain = str(
            [("categ_id", "=", self.categorie.id)]
        )
        self.assertEqual(self.attribute.value_ids.mapped("product_id"), self.poignees)
        for valeur in self.attribute.value_ids:
            self.assertTrue(valeur.configurator_generated)

    # ── ce que le filtre DONNE, avant de s'en servir (D-208) ────────────────
    def test_07_the_count_says_how_many_come_out(self):
        """⚠️ Un domaine est une promesse tant qu'on ne l'a pas appliqué.

        Écrit sans retour, il se vérifie au pire moment — devant le client,
        quand la liste proposée est vide ou compte trois cents lignes.
        """
        self.attribute.product_filter_domain = str(
            [("categ_id", "=", self.categorie.id)]
        )
        self.assertEqual(self.attribute.product_filter_count, len(self.poignees))

    def test_08_and_it_says_ZERO_when_nothing_is_filtered(self):
        self.assertEqual(self.attribute.product_filter_count, 0)

    def test_09_the_count_NEVER_raises_while_typing(self):
        """⚠️ Le calcul tourne à CHAQUE FRAPPE dans l'éditeur de domaine.

        Un domaine à moitié écrit est la règle, pas l'exception : une exception
        ici casserait le formulaire au lieu d'attendre. Le refus se fait à
        l'enregistrement, où `_check_product_filter` dit non avec ses mots.

        ⓘ On écrit donc en SQL — l'ORM refuserait précisément ce qu'on veut
        éprouver, à savoir un domaine invalide en cours de saisie.
        """
        self.env.cr.execute(
            "UPDATE product_attribute SET product_filter_domain = %s WHERE id = %s",
            ("[('champ_inexistant', '=', 1)]", self.attribute.id),
        )
        self.attribute.invalidate_recordset()
        self.assertEqual(self.attribute.product_filter_count, 0)

    def test_10_the_results_open_in_a_DIALOG(self):
        """Comme les valeurs (D-206) : on revient là où on l'a ouvert."""
        self.attribute.product_filter_domain = str(
            [("categ_id", "=", self.categorie.id)]
        )
        action = self.attribute.action_open_proposed_products()
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["res_model"], "product.product")
        trouves = self.env["product.product"].search(action["domain"])
        self.assertEqual(trouves, self.poignees)

    # ── le MODE : liste tenue, ou liste proposée (D-218) ────────────────────
    def test_11_a_filter_proposes_NOTHING_without_the_dynamic_mode(self):
        """⚠️ Décocher « valeurs dynamiques » doit rendre le filtre INERTE.

        Sans cela, un filtre resté en base agirait dans l'ombre : la liste
        paraîtrait tenue à la main et serait alimentée en secret. Les deux
        régimes coexistent — soit on tient la liste, soit un filtre la propose —
        et un champ dit lequel.
        """
        self.attribute.dynamic_values = True
        self.attribute.product_filter_domain = str(
            [("categ_id", "=", self.categorie.id)]
        )
        self.assertEqual(self.attribute._proposed_products(), self.poignees)

        # ⓘ En SQL : l'onchange nettoierait le filtre, or c'est justement le cas
        # « un filtre reste en base » que la garde doit tenir.
        #
        # ⚠️ **VIDER LE TAMPON D'ABORD.** Les écritures ORM ci-dessus ne sont pas
        # encore en base : sans `flush_all`, l'`UPDATE` passe, puis le flush les
        # réécrit PAR-DESSUS — et la garde échoue sur un code juste. Mesuré.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE product_attribute SET dynamic_values = false WHERE id = %s",
            (self.attribute.id,),
        )
        self.attribute.invalidate_recordset()
        self.assertFalse(self.attribute._proposed_products())
        self.assertEqual(self.attribute.product_filter_count, 0)

    def test_12_the_dynamic_mode_belongs_to_the_PRODUCT_type(self):
        """QK : une condition vérifie l'égalité sur des produits, et un filtre ne
        sait proposer que cela."""
        plain = self.env["product.attribute"].create({
            "name": "Plain dyn", "create_variant": "no_variant", "value_type": "value",
        })
        with self.assertRaises(ValidationError):
            plain.dynamic_values = True

    def test_13_leaving_the_product_type_CLEARS_the_mode_and_its_filter(self):
        """⚠️ Sinon la coche et son filtre restent en base, invisibles.

        Le refus tomberait alors sur un champ que l'utilisateur ne voit plus —
        le pire des messages d'erreur (D-194). Éprouvé par `Form`, seul chemin
        où un onchange existe ([[L-157]]).
        """
        from odoo.tests.common import Form

        self.attribute.dynamic_values = True
        self.attribute.product_filter_domain = str(
            [("categ_id", "=", self.categorie.id)]
        )
        with Form(self.attribute) as f:
            f.value_type = "value"
        self.assertFalse(self.attribute.dynamic_values)
        self.assertEqual(self.attribute.product_filter_domain, "[]")

    def test_14_and_unticking_the_mode_clears_the_filter_too(self):
        """ⓘ Revenir à une liste tenue à la main : le filtre n'a plus d'objet."""
        from odoo.tests.common import Form

        self.attribute.dynamic_values = True
        self.attribute.product_filter_domain = str(
            [("categ_id", "=", self.categorie.id)]
        )
        with Form(self.attribute) as f:
            f.dynamic_values = False
        self.assertEqual(self.attribute.product_filter_domain, "[]")
