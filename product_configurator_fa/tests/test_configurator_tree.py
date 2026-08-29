"""L'arbre du configurateur — la maquette de Gerry (D-210).

⚠️ Trois natures de lignes dans une seule liste : l'ÉTAPE en bandeau, l'ATTRIBUT,
et ses VALEURS indentées. Une liste Odoo ne sait ni s'imbriquer ni mêler deux
modèles — d'où un composant, et d'où cette structure rendue par le serveur.
"""

from odoo.exceptions import UserError

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

    # ── ce que l'arbre peut FAIRE — D-211 ───────────────────────────────────
    def _domaine(self, nom="Rule tree"):
        domaine = self.env["product.config.domain"].create({"name": nom})
        self.env["product.config.domain.line"].create([
            {"domain_id": domaine.id, "attribute_id": self.shape.id,
             "value_ids": [(6, 0, self.round.ids)], "condition": "in",
             "operator": "and", "sequence": 10},
            {"domain_id": domaine.id, "attribute_id": self.kind.id,
             "value_ids": [(6, 0, self.cine.ids)], "condition": "in",
             "operator": "and", "sequence": 20},
        ])
        return domaine

    def test_07_a_facet_carries_the_RULE_it_would_remove(self):
        """⚠️ Sans cet identifiant, le seul geste serait « tout effacer ».

        Une condition à trois règles se perdrait pour en corriger une — alors
        que le geste demandé est celui de la barre de recherche, où chaque
        pastille s'enlève seule.
        """
        ligne = self.template.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.kind
        )
        ligne.visibility_domain_id = self._domaine()
        attributs = [r for r in self._rows() if r["kind"] == "attribute"]
        facettes = attributs[0]["facets"]
        self.assertEqual(len(facettes), 2)
        self.assertTrue(all(f["id"] and f["label"] for f in facettes))

    def test_08_the_cross_removes_ONE_rule_and_keeps_the_others(self):
        ligne = self.template.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.kind
        )
        domaine = self._domaine()
        ligne.visibility_domain_id = domaine
        premiere = self._rows()[0]["facets"][0]
        self.template.configurator_remove_facet(premiere["id"])
        restantes = self._rows()[0]["facets"]
        self.assertEqual(len(restantes), 1)
        self.assertNotIn(premiere["id"], [f["id"] for f in restantes])

    def test_09_and_the_EMPTY_condition_stays(self):
        """⚠️ Elle porte un nom et peut être partagée.

        La supprimer parce qu'on a retiré sa dernière règle serait décider à la
        place de l'utilisateur — et casser les autres produits qui l'emploient.
        """
        ligne = self.template.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.kind
        )
        domaine = self._domaine()
        ligne.visibility_domain_id = domaine
        for facette in list(self._rows()[0]["facets"]):
            self.template.configurator_remove_facet(facette["id"])
        self.assertTrue(domaine.exists())
        self.assertEqual(ligne.visibility_domain_id, domaine)

    def test_10_removing_a_VALUE_goes_through_the_line(self):
        """ⓘ C'est le chemin ordinaire, donc celui qui déclenche les deux visages.

        Détruire la valeur du produit directement court-circuiterait le filet de
        D-205 — supprimer si possible, désactiver sinon.
        """
        ligne = self.template.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.kind
        )
        self.template.configurator_remove_value(ligne.id, self.cine.id)
        self.assertNotIn(self.cine, ligne.value_ids)
        self.assertIn(self.classic, ligne.value_ids)

    def test_11_removing_a_STEP_clears_the_marker_not_the_step(self):
        """⚠️ L'étape est partagée entre produits — on retire le MARQUEUR.

        Et ce qui suivait rejoint l'étape précédente, ou aucune : c'est la
        contrepartie du séparateur, visible tout de suite.
        """
        ligne = self.template.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.shape
        )
        self.template.configurator_clear_step(ligne.id)
        self.assertTrue(self.step.exists(), "l'étape elle-même a été détruite")
        self.assertFalse(ligne.config_step_id)
        self.assertNotIn("step", [r["kind"] for r in self._rows()])

    def test_12_reordering_writes_the_sequences_in_the_given_order(self):
        lignes = self.template.attribute_line_ids.sorted()
        inverse = list(reversed(lignes.ids))
        self.template.configurator_reorder(inverse)
        self.assertEqual(self.template.attribute_line_ids.sorted().ids, inverse)

    def test_13_and_moving_a_line_MOVES_ITS_STEP_TOO(self):
        """⚠️ L'ordre porte l'appartenance : déplacer, c'est réaffecter.

        La ligne qui ouvre l'étape passant en tête, le bandeau ouvre l'arbre et
        l'autre attribut lui appartient désormais. C'est assumé (D-202), et
        l'arbre le redessine tout de suite.
        """
        lignes = self.template.attribute_line_ids.sorted()
        self.template.configurator_reorder(list(reversed(lignes.ids)))
        genres = [r["kind"] for r in self._rows()]
        self.assertEqual(genres, ["step", "attribute", "attribute"])

    def test_14_the_line_SETTINGS_have_a_door_at_last(self):
        """⚠️ Ils n'étaient joignables NULLE PART depuis la fiche produit — D-217.

        Constat de Gerry : *« je ne vois pas comment modifier price_mode dans la
        fiche produit »*. Vérifié : le bouton « Configurer » du cœur ouvre les
        VALEURS (`action_open_attribute_values`), pas la ligne. Or c'est la ligne
        qui porte le mode de prix, le rôle de dimension, les bornes et la vue 3D
        — et c'est **elle** qui est lue à l'exécution, pas la semence de
        l'attribut.
        """
        ligne = self.template.attribute_line_ids[:1]
        action = ligne.action_open_configurator_line()
        self.assertEqual(action["res_model"], "product.template.attribute.line")
        self.assertEqual(action["res_id"], ligne.id)
        self.assertEqual(action["target"], "new")

    def test_15_and_it_opens_the_CORE_view_so_every_module_is_there(self):
        """⚠️ Nommer la vue héritée ignorerait les greffons des AUTRES modules.

        La vue du cœur porte, par héritage, nos réglages ET ceux du pont 3D. La
        désigner nommément — plutôt que notre vue dérivée — est ce qui garantit
        que la caméra du pont s'affiche aussi ([[L-167]]).
        """
        ligne = self.template.attribute_line_ids[:1]
        action = ligne.action_open_configurator_line()
        self.assertEqual(
            action["views"],
            [(self.env.ref("product.product_template_attribute_line_form").id, "form")],
        )

    # ─ RÉORDONNER LES VALEURS D'UN ATTRIBUT — 2026-08-29 ────────────────────
    #
    # ⚠️ **CET ORDRE EST GLOBAL, ET C'EST ASSUMÉ.** Le rang d'une valeur vit
    # dans `product.attribute.value.sequence`, qui appartient à l'ATTRIBUT et
    # non au produit. Arbitré par Gerry : c'est le seul ordre qui existe, et en
    # inventer un par produit obligerait tout ce qui affiche des valeurs à le
    # relire (assistant, arbre, éditeur 3D).

    def test_16_reordering_VALUES_rewrites_the_order_the_tree_shows(self):
        ligne = self.template.attribute_line_ids.filtered(
            lambda ligne: ligne.attribute_id == self.kind
        )
        self.template.configurator_reorder_values(
            ligne.id, [self.cine.id, self.classic.id]
        )
        attribut = [r for r in self._rows() if r["kind"] == "attribute"][0]
        self.assertEqual([v["name"] for v in attribut["values"]], ["Ciné", "Classic"])

    def test_17_and_it_reorders_the_ATTRIBUTE_so_every_product_follows(self):
        """⚠️ Le prix de la simplicité : un seul ordre, partagé.

        Déplacer une valeur depuis un produit la déplace partout où l'attribut
        sert. C'est ce que Gerry a choisi le 2026-08-29 ; le test existe pour que
        personne ne « corrige » ce comportement en le prenant pour un bug.
        """
        autre = self.env["product.template"].create({
            "name": "Second panel", "config_ok": True,
            "attribute_line_ids": [
                (0, 0, {"attribute_id": self.kind.id,
                        "value_ids": [(6, 0, (self.classic + self.cine).ids)]}),
            ],
        })
        ligne = self.template.attribute_line_ids.filtered(
            lambda ligne: ligne.attribute_id == self.kind
        )
        self.template.configurator_reorder_values(
            ligne.id, [self.cine.id, self.classic.id]
        )
        self.assertEqual(
            [v["name"] for v in autre.get_configurator_tree()[0]["values"]],
            ["Ciné", "Classic"],
        )

    def test_18_a_value_the_product_does_NOT_carry_keeps_its_rank(self):
        """⚠️ Un produit ne porte souvent qu'une PART des valeurs de l'attribut.

        Renuméroter les seules valeurs du produit (10, 20, 30) les jetterait
        devant celles qu'il n'emploie pas, restées à leur propre séquence. On
        renumérote donc l'attribut entier, en ne permutant les valeurs demandées
        qu'entre les RANGS qu'elles occupaient déjà.
        """
        # « Freestyle » se glisse ENTRE Classic et Ciné, et n'est pas sur le
        # produit : il doit rester au milieu, quoi qu'on fasse des deux autres.
        self.classic.sequence, self.cine.sequence = 10, 30
        freestyle = self.env["product.attribute.value"].create(
            {"name": "Freestyle", "attribute_id": self.kind.id, "sequence": 20}
        )
        ligne = self.template.attribute_line_ids.filtered(
            lambda ligne: ligne.attribute_id == self.kind
        )
        self.template.configurator_reorder_values(
            ligne.id, [self.cine.id, self.classic.id]
        )
        self.assertEqual(
            self.kind.value_ids.mapped("name"), ["Ciné", "Freestyle", "Classic"]
        )
        self.assertEqual(freestyle.sequence, 20)

    def test_19_a_value_that_is_NOT_on_the_line_is_REFUSED(self):
        """⚠️ Sans ce garde-fou, un identifiant venu d'ailleurs réordonnerait un
        attribut que l'écran ne montrait même pas."""
        ligne = self.template.attribute_line_ids.filtered(
            lambda ligne: ligne.attribute_id == self.kind
        )
        with self.assertRaises(UserError):
            self.template.configurator_reorder_values(
                ligne.id, [self.cine.id, self.classic.id, self.round.id]
            )
