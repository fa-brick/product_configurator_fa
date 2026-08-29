"""Le FILTRE alimente l'assistant, et ce qu'il propose est MATÉRIALISÉ — C3, D-221.

⚠️ Arbitrage de Gerry : *« on va partir sur 1, le filtre qui alimente
l'assistant »*. La liste de la ligne cesse alors d'être un catalogue à tenir pour
devenir la **trace** de ce qui a été choisi (QJ) — et c'est ce qui rend la notion
tenable : la valeur retenue est une `product.attribute.value` ordinaire, donc
prix, archivage, exclusions et historique continuent de fonctionner.
"""

from odoo.addons.base.tests.common import BaseCommon


class DynamicMaterialisation(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.categorie = cls.env["product.category"].create({"name": "Handles C3"})
        cls.poignees = cls.env["product.product"].create([
            {"name": "Handle A3", "categ_id": cls.categorie.id},
            {"name": "Handle B3", "categ_id": cls.categorie.id},
        ])
        cls.attribute = cls.env["product.attribute"].create({
            "name": "Handle dyn", "create_variant": "no_variant",
            "value_type": "product", "dynamic_values": True,
            "product_filter_domain": str([("categ_id", "=", cls.categorie.id)]),
        })
        cls.amorce = cls.env["product.attribute.value"].create({
            "name": "Seed", "attribute_id": cls.attribute.id,
        })
        cls.template = cls.env["product.template"].create({
            "name": "Door dyn", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": cls.attribute.id,
                "value_ids": [(6, 0, cls.amorce.ids)],
            })],
        })
        cls.line = cls.template.attribute_line_ids

    def test_01_each_proposed_product_GETS_a_value(self):
        valeurs = self.attribute._materialise_proposed_values()
        self.assertEqual(valeurs.mapped("product_id"), self.poignees)
        for valeur in valeurs:
            self.assertTrue(valeur.configurator_generated)

    def test_02_and_it_is_IDEMPOTENT(self):
        """⚠️ L'assistant l'appelle à CHAQUE ouverture.

        Sans réemploi par `product_id`, chaque visite créerait un jumeau, et le
        catalogue enflerait d'une valeur par consultation.
        """
        premieres = self.attribute._materialise_proposed_values()
        secondes = self.attribute._materialise_proposed_values()
        self.assertEqual(premieres, secondes)
        self.assertEqual(
            len(self.attribute.value_ids), 1 + len(self.poignees),
            "des jumelles ont été créées",
        )

    def test_03_an_ARCHIVED_value_is_revived_not_duplicated(self):
        """ⓘ Même geste que pour une saisie libre qui revient (D-082)."""
        valeurs = self.attribute._materialise_proposed_values()
        valeurs[0].active = False
        rendues = self.attribute._materialise_proposed_values()
        self.assertTrue(valeurs[0].active)
        self.assertEqual(rendues, valeurs)

    def test_04_the_LINE_offers_the_filter_not_just_its_own_list(self):
        """⚠️ C'est le cœur de C3 : le filtre alimente l'assistant."""
        offertes = self.line._configurator_value_ids()
        self.assertIn(self.amorce, offertes)
        for produit in self.poignees:
            self.assertTrue(
                offertes.filtered(lambda v, p=produit: v.product_id == p),
                f"{produit.display_name} n'est pas proposé",
            )

    def test_05_a_value_ALREADY_CHOSEN_stays_offered_if_the_filter_changes(self):
        """⚠️ On rend l'UNION, et non le seul filtre.

        Sinon une configuration en cours perdrait son choix le jour où le filtre
        se resserre, et une reconfiguration deviendrait impossible.
        """
        valeurs = self.attribute._materialise_proposed_values()
        retenue = valeurs[0]
        self.line.value_ids = [(4, retenue.id)]
        self.attribute.product_filter_domain = str([("id", "=", 0)])
        offertes = self.line._configurator_value_ids()
        self.assertIn(retenue, offertes)

    def test_06_a_NON_dynamic_attribute_is_untouched(self):
        """ⓘ Sur tous les autres, la méthode rend exactement `value_ids`."""
        attribut = self.env["product.attribute"].create(
            {"name": "Plain C3", "create_variant": "no_variant"}
        )
        valeur = self.env["product.attribute.value"].create(
            {"name": "One", "attribute_id": attribut.id}
        )
        gabarit = self.env["product.template"].create({
            "name": "Plain door", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": attribut.id,
                "value_ids": [(6, 0, valeur.ids)],
            })],
        })
        ligne = gabarit.attribute_line_ids
        self.assertEqual(ligne._configurator_value_ids(), ligne.value_ids)

    def test_07_the_WIZARD_offers_them(self):
        """⚠️ Le modèle ne suffit pas : c'est l'assistant qui devait changer.

        La garde ouvre l'assistant et lit le domaine du champ dynamique — sans
        quoi on aurait éprouvé une méthode que personne n'appelle.
        """
        wizard = self.env["product.configurator"].create(
            {"product_tmpl_id": self.template.id}
        )
        domaines = wizard.with_context(wizard_id=wizard.id).get_onchange_domains(
            cfg_val_ids=[], product_tmpl_id=self.template
        )
        nom = f"{wizard._prefixes['field_prefix']}{self.attribute.id}"
        self.assertIn(nom, domaines)
        # ⓘ La forme rendue est un domaine nu : `[("id", "in", [...])]`.
        proposes = domaines[nom][0][2]
        materialisees = self.attribute._materialise_proposed_values()
        for valeur in materialisees:
            self.assertIn(valeur.id, proposes)

    # ── ce qui se matérialise TOUT SEUL (D-222) ─────────────────────────────
    def test_08_posing_the_filter_fills_the_ATTRIBUTE_values(self):
        """⚠️ Demande de Gerry : voir les enregistrements du filtre dans la liste.

        Sans cela, les valeurs n'apparaissaient qu'à la première ouverture de
        l'assistant : la page d'attribut montrait une liste vide alors que le
        filtre annonçait cinquante-trois produits — deux écrans qui se
        contredisent.
        """
        neuf = self.env["product.attribute"].create({
            "name": "Handle posed", "create_variant": "no_variant",
            "value_type": "product", "dynamic_values": True,
        })
        self.assertFalse(neuf.value_ids)
        neuf.product_filter_domain = str([("categ_id", "=", self.categorie.id)])
        self.assertEqual(neuf.value_ids.mapped("product_id"), self.poignees)

    def test_09_a_dynamic_LINE_is_born_with_them(self):
        """⚠️ Le cœur exige au moins une valeur par ligne.

        Une ligne dynamique fraîche était donc impossible à créer sans choisir
        d'abord une valeur à la main — sur un attribut dont tout l'objet est de
        ne pas tenir de liste.
        """
        gabarit = self.env["product.template"].create({
            "name": "Door born", "config_ok": True,
            "attribute_line_ids": [(0, 0, {"attribute_id": self.attribute.id})],
        })
        ligne = gabarit.attribute_line_ids
        self.assertTrue(ligne.value_ids, "la ligne est née sans valeur")
        for produit in self.poignees:
            self.assertTrue(
                ligne.value_ids.filtered(lambda v, p=produit: v.product_id == p)
            )

    def test_10_but_an_EXPLICIT_choice_keeps_the_last_word(self):
        """ⓘ On ne remplit que si rien n'est fourni."""
        gabarit = self.env["product.template"].create({
            "name": "Door chosen", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": self.attribute.id,
                "value_ids": [(6, 0, self.amorce.ids)],
            })],
        })
        self.assertEqual(gabarit.attribute_line_ids.value_ids, self.amorce)

    def test_11_a_NON_dynamic_line_is_not_filled(self):
        """La règle ne vaut que pour le régime dynamique."""
        attribut = self.env["product.attribute"].create(
            {"name": "Plain born", "create_variant": "no_variant"}
        )
        valeur = self.env["product.attribute.value"].create(
            {"name": "One", "attribute_id": attribut.id}
        )
        gabarit = self.env["product.template"].create({
            "name": "Plain born door", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": attribut.id,
                "value_ids": [(6, 0, valeur.ids)],
            })],
        })
        self.assertEqual(gabarit.attribute_line_ids.value_ids, valeur)


class RetractionDuFiltre(BaseCommon):
    """⚠️ **Ce qu'un filtre PRÉCÉDENT a proposé s'en va** — constat de Gerry :

    *« j'ai un résultat, et plusieurs produits dans la liste »*. La
    matérialisation (D-222) était idempotente mais ne se **rétractait** jamais :
    chaque essai laissait ses valeurs derrière lui, et la liste finissait par
    contredire le compteur qui l'annonçait.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.categ_a = cls.env["product.category"].create({"name": "Retract A"})
        cls.categ_b = cls.env["product.category"].create({"name": "Retract B"})
        cls.produit_a = cls.env["product.product"].create(
            {"name": "Only in A", "categ_id": cls.categ_a.id}
        )
        cls.produit_b = cls.env["product.product"].create(
            {"name": "Only in B", "categ_id": cls.categ_b.id}
        )
        cls.attribut = cls.env["product.attribute"].create({
            "name": "Retracting attribute",
            "value_type": "product",
            "dynamic_values": True,
            "create_variant": "no_variant",
            "product_filter_domain": str([("categ_id", "=", cls.categ_a.id)]),
        })

    def _basculer_sur_b(self):
        self.attribut.product_filter_domain = str(
            [("categ_id", "=", self.categ_b.id)]
        )

    def test_01_changer_de_filtre_RETIRE_ce_qu_il_ne_propose_plus(self):
        self.assertEqual(self.attribut.value_ids.product_id, self.produit_a)
        self._basculer_sur_b()
        self.assertEqual(self.attribut.value_ids.product_id, self.produit_b)

    def test_02_une_valeur_ECRITE_A_LA_MAIN_survit(self):
        """Elle n'a jamais été proposée par un filtre : ce n'est pas à lui de la

        reprendre.
        """
        main = self.env["product.attribute.value"].create(
            {"name": "Written by hand", "attribute_id": self.attribut.id}
        )
        self._basculer_sur_b()
        self.assertIn(main, self.attribut.value_ids)

    def test_03_une_valeur_RETENUE_sur_un_produit_survit(self):
        """⚠️ QJ pose que la valeur choisie est matérialisée. La retirer parce

        que le filtre a changé casserait la ligne d'un produit en service, en
        silence.
        """
        valeur_a = self.attribut.value_ids
        self.env["product.template.attribute.line"].create({
            "product_tmpl_id": self.env["product.template"].create(
                {"name": "Uses A", "config_ok": True}
            ).id,
            "attribute_id": self.attribut.id,
            "value_ids": [(6, 0, valeur_a.ids)],
        })
        self._basculer_sur_b()
        self.assertIn(valeur_a, self.attribut.value_ids)

    def test_04_un_produit_DESIGNE_par_une_condition_survit(self):
        """⚠️ La règle se résout par cette valeur (C4) : l'effacer rendrait la

        condition vide — donc toujours fausse — sans un mot.
        """
        valeur_a = self.attribut.value_ids
        self.env["product.config.domain"].create({
            "name": "Uses A",
            "domain_line_ids": [(0, 0, {
                "attribute_id": self.attribut.id,
                "condition": "in",
                "product_ids": [(6, 0, self.produit_a.ids)],
            })],
        })
        self._basculer_sur_b()
        self.assertIn(valeur_a, self.attribut.value_ids)

    def test_05_hors_du_regime_dynamique_on_ne_retire_RIEN(self):
        """La liste est alors tenue à la main, et le filtre n'a plus voix au

        chapitre (D-218) — décocher le mode ne doit pas la vider.
        """
        valeur_a = self.attribut.value_ids
        self.attribut.dynamic_values = False
        self.attribut._materialise_proposed_values()
        self.assertIn(valeur_a, self.attribut.value_ids)
