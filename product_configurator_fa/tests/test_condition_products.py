from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon


class ConditionOnProducts(BaseCommon):
    """C4 — une condition qui désigne des PRODUITS (D-201).

    L'arbitrage de Gerry : *« les conditions portent sur les valeurs d'attribut
    ET sur les produits. »* Les deux formes coexistent ; celle-ci ne remplace
    rien.

    ⚠️ **Ce que la forme « produit » rend possible, et que l'autre ne permet
    pas.** Sur un attribut à valeurs dynamiques, les valeurs n'existent
    qu'après avoir été proposées : une règle écrite sur des valeurs serait
    **impossible à saisir** tant que le catalogue est vide. Le produit, lui,
    existe toujours.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chene = cls.env["product.product"].create({"name": "Oak panel"})
        cls.hetre = cls.env["product.product"].create({"name": "Beech panel"})
        cls.attr_panneau = cls.env["product.attribute"].create(
            {
                "name": "Panel",
                "value_type": "product",
                "create_variant": "no_variant",
            }
        )
        cls.attr_finition = cls.env["product.attribute"].create(
            {"name": "Finish", "create_variant": "no_variant"}
        )
        cls.mate = cls.env["product.attribute.value"].create(
            {"name": "Matt", "attribute_id": cls.attr_finition.id}
        )

    def _regle_produit(self, produits, condition="in"):
        return self.env["product.config.domain"].create(
            {
                "name": "Panel rule",
                "domain_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": self.attr_panneau.id,
                            "condition": condition,
                            "product_ids": [(6, 0, produits.ids)],
                        },
                    )
                ],
            }
        )

    def test_01_designer_un_produit_MATERIALISE_sa_valeur(self):
        """Enregistrer la règle crée la valeur — l'évaluation ne doit rien écrire.

        ⓘ Même geste que le filtre dynamique (D-222), et pour la même raison :
        matérialiser à la volée écrirait en base au milieu d'une configuration,
        y compris dans un contexte en lecture seule.
        """
        self._regle_produit(self.chene)
        valeurs = self.attr_panneau.value_ids.filtered(
            lambda v: v.product_id == self.chene
        )
        self.assertEqual(len(valeurs), 1)
        self.assertTrue(valeurs.configurator_generated)

    def test_02_la_feuille_produit_se_RESOUT_en_valeurs(self):
        """Un seul moteur d'évaluation : la ligne rend des ids de VALEURS.

        ⚠️ Si `compute_domain` lisait `value_ids` en direct, une feuille
        « produit » sortirait VIDE — donc un `in` qui ne matche jamais et un
        `not in` qui matche toujours. Sans un mot.
        """
        regle = self._regle_produit(self.chene)
        valeur = self.attr_panneau.value_ids.filtered(
            lambda v: v.product_id == self.chene
        )
        self.assertEqual(
            regle.compute_domain(),
            [(self.attr_panneau.id, "in", valeur.ids)],
        )

    def test_03_elle_ne_resout_QUE_les_produits_designes(self):
        self._regle_produit(self.hetre)          # matérialise le hêtre aussi
        regle = self._regle_produit(self.chene)
        (_attribut, _condition, ids), = regle.compute_domain()
        self.assertEqual(
            self.env["product.attribute.value"].browse(ids).product_id,
            self.chene,
        )

    def test_04_l_aller_retour_vers_l_editeur_GARDE_la_forme(self):
        """⚠️ La régression qui compte : une règle « produit » qui revient en

        règle « valeur ». Elle se serait mise à désigner des valeurs FIGÉES là
        où son auteur avait désigné des produits — et sur un attribut dynamique,
        c'est précisément ce qu'on voulait éviter. D'où un préfixe de champ
        distinct côté éditeur.
        """
        regle = self._regle_produit(self.chene | self.hetre)
        domaine = regle.to_odoo_domain()
        champ = self.env["product.config.domain"]._product_field_name(
            self.attr_panneau
        )
        self.assertEqual(domaine[0][0], champ)
        regle.from_odoo_domain(domaine)
        self.assertEqual(regle.domain_line_ids.product_ids, self.chene | self.hetre)
        self.assertFalse(regle.domain_line_ids.value_ids)
        self.assertEqual(regle.to_odoo_domain(), domaine)

    def test_05_les_deux_formes_COEXISTENT_dans_une_meme_regle(self):
        """D-201 : « C4 ajoute une seconde forme, il n'en remplace aucune. »"""
        regle = self.env["product.config.domain"].create(
            {
                "name": "Mixed",
                "domain_line_ids": [
                    (0, 0, {
                        "attribute_id": self.attr_panneau.id,
                        "condition": "in",
                        "product_ids": [(6, 0, self.chene.ids)],
                        "sequence": 1,
                    }),
                    (0, 0, {
                        "attribute_id": self.attr_finition.id,
                        "condition": "in",
                        "value_ids": [(6, 0, self.mate.ids)],
                        "sequence": 2,
                    }),
                ],
            }
        )
        domaine = regle.compute_domain()
        self.assertEqual(len(domaine), 2)
        self.assertEqual(domaine[1], (self.attr_finition.id, "in", self.mate.ids))

    def test_06_une_ligne_designe_l_un_OU_l_autre_jamais_les_deux(self):
        """⚠️ `value_ids` ne peut plus être `required` — cette garde le remplace.

        Sans elle, une ligne VIDE passerait : une condition vide n'exclut rien,
        et la règle serait sans effet sans que rien ne le dise.
        """
        with self.assertRaises(ValidationError):
            self.env["product.config.domain"].create({
                "name": "Empty leaf",
                "domain_line_ids": [
                    (0, 0, {"attribute_id": self.attr_panneau.id, "condition": "in"})
                ],
            })
        with self.assertRaises(ValidationError):
            self.env["product.config.domain"].create({
                "name": "Both forms",
                "domain_line_ids": [(0, 0, {
                    "attribute_id": self.attr_finition.id,
                    "condition": "in",
                    "value_ids": [(6, 0, self.mate.ids)],
                    "product_ids": [(6, 0, self.chene.ids)],
                })],
            })

    def test_07_la_pastille_nomme_les_PRODUITS_pas_les_valeurs(self):
        """C'est ce que son auteur a écrit qu'on lui relit."""
        regle = self._regle_produit(self.chene)
        self.assertIn(self.chene.display_name, regle.condition_summary)

    def test_08_changer_d_attribut_VIDE_la_feuille(self):
        """Sinon la ligne garde les désignations de l'attribut précédent —

        `_resolved_value_ids` rendrait des valeurs étrangères à l'attribut
        testé, et la condition ne pourrait plus être vraie.
        """
        from odoo.tests import Form

        regle = self._regle_produit(self.chene)
        with Form(regle) as formulaire:
            with formulaire.domain_line_ids.edit(0) as ligne:
                ligne.attribute_id = self.attr_finition
                self.assertFalse(ligne.product_ids)
                ligne.value_ids.add(self.mate)
        self.assertEqual(regle.domain_line_ids.value_ids, self.mate)
