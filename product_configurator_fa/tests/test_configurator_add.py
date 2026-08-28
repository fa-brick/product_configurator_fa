"""Ajouter depuis l'arbre — D-212.

⚠️ *« Une liste vide sans point d'entrée se lit comme une panne. »* Constaté par
Gerry à l'écran : l'arbre s'affichait vide sur un produit sans attribut, et rien
ne disait quoi faire.
"""

from odoo.exceptions import UserError

from odoo.addons.base.tests.common import BaseCommon


class ConfiguratorAdd(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.step = cls.env["product.config.step"].create({"name": "Finishing"})
        cls.attribute = cls.env["product.attribute"].create(
            {"name": "Finish add", "create_variant": "no_variant"}
        )
        cls.value = cls.env["product.attribute.value"].create(
            {"name": "Matt", "attribute_id": cls.attribute.id}
        )
        cls.empty = cls.env["product.template"].create(
            {"name": "Empty product", "config_ok": True}
        )
        cls.filled = cls.env["product.template"].create({
            "name": "Filled product", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": cls.attribute.id,
                "value_ids": [(6, 0, cls.value.ids)],
            })],
        })

    def test_01_adding_an_attribute_opens_the_LINE_form(self):
        """ⓘ La ligne, pas une liste d'attributs : un attribut sans valeur ne
        serait pas une ligne valide pour le cœur — on choisit les deux d'un coup.
        """
        action = self.empty.action_configurator_add_attribute()
        self.assertEqual(action["res_model"], "product.template.attribute.line")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_product_tmpl_id"], self.empty.id)

    def test_10_l_assistant_est_utilisable_par_un_GESTIONNAIRE_pas_seulement_admin(self):
        """⚠️ Le modèle n'avait AUCUNE règle d'accès — Odoo le disait à chaque

        démarrage, et je l'avais laissé passer. Un `TransientModel` sans droits
        est ouvert au superutilisateur seul : tous les tests passaient, et le
        bouton aurait levé « accès refusé » chez le premier gestionnaire à s'en
        servir. Cette couture s'exécute SOUS un utilisateur réel — c'est tout
        l'objet.
        """
        gestionnaire = self.env["res.users"].create({
            "name": "Config manager",
            "login": "cfg_manager_acl",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref(
                    "product_configurator_fa"
                    ".group_product_configurator_fa_manager"
                ).id,
            ])],
        })
        assistant = (
            self.env["product.configurator.add.step"]
            .with_user(gestionnaire)
            .create({
                "product_tmpl_id": self.filled.id,
                "config_step_id": self.step.id,
                "attribute_line_id": self.filled.attribute_line_ids[0].id,
            })
        )
        self.assertTrue(assistant.id)

    def test_02_adding_a_step_on_an_EMPTY_product_explains_why_it_cannot(self):
        """⚠️ C'est la contrepartie de la forme (A) : une étape ne flotte pas.

        Elle s'ouvre SUR un attribut. Sans attribut, il n'y a rien à ouvrir — et
        il vaut mieux le dire que rendre un bouton inerte.
        """
        with self.assertRaises(UserError):
            self.empty.action_configurator_add_step()

    def test_03_and_opens_an_assistant_when_there_is_something_to_open_on(self):
        action = self.filled.action_configurator_add_step()
        self.assertEqual(action["res_model"], "product.configurator.add.step")
        self.assertEqual(action["target"], "new")

    def test_04_the_assistant_proposes_the_first_FREE_line(self):
        """⚠️ LIBRE, et pas simplement « la première ».

        Proposer une ligne qui porte déjà une étape couperait cette étape en
        deux par inadvertance. ⓘ Le produit de ce test porte donc DEUX lignes,
        la première déjà marquée : avec un seul attribut, « la première » et
        « la première libre » se confondent, et la garde ne prouverait rien.
        """
        second = self.env["product.attribute"].create(
            {"name": "Second add", "create_variant": "no_variant"}
        )
        valeur = self.env["product.attribute.value"].create(
            {"name": "Gloss", "attribute_id": second.id}
        )
        deuxieme = self.env["product.template.attribute.line"].create({
            "product_tmpl_id": self.filled.id,
            "attribute_id": second.id,
            "value_ids": [(6, 0, valeur.ids)],
            "sequence": 20,
        })
        premiere = self.filled.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.attribute
        )
        premiere.write({"sequence": 10, "config_step_id": self.step.id})

        assistant = self.env["product.configurator.add.step"].with_context(
            default_product_tmpl_id=self.filled.id
        ).create({"config_step_id": self.step.id})
        self.assertEqual(
            assistant.attribute_line_id, deuxieme,
            "l'assistant propose une ligne qui porte déjà une étape",
        )

    def test_05_applying_it_marks_the_line_and_the_tree_shows_the_band(self):
        assistant = self.env["product.configurator.add.step"].with_context(
            default_product_tmpl_id=self.filled.id
        ).create({
            "config_step_id": self.step.id,
            "attribute_line_id": self.filled.attribute_line_ids.id,
        })
        assistant.action_apply()
        self.assertEqual(
            self.filled.attribute_line_ids.config_step_id, self.step
        )
        self.assertIn("step", [r["kind"] for r in self.filled.get_configurator_tree()])

    def test_06_a_line_of_ANOTHER_product_is_refused(self):
        """⚠️ Le domaine de la vue le filtre déjà ; ceci est la seconde barrière.

        Celle qui ne dépend pas de l'interface (D-080) — un import ou un script
        ne passe pas par la vue.
        """
        assistant = self.env["product.configurator.add.step"].with_context(
            default_product_tmpl_id=self.empty.id
        ).create({
            "product_tmpl_id": self.empty.id,
            "config_step_id": self.step.id,
            "attribute_line_id": self.filled.attribute_line_ids.id,
        })
        with self.assertRaises(UserError):
            assistant.action_apply()


class ConfiguratorConditions(BaseCommon):
    """Poser une condition depuis l'arbre — D-213.

    ⚠️ Question de Gerry : *« Configuration Restrictions n'a plus d'utilité ? »*
    La réponse était **si, jusqu'à ce que l'arbre sache le faire** : c'était le
    seul endroit d'où l'on crée une condition PAR VALEUR. Ces gardes sont ce qui
    a rendu son retrait possible sans rien perdre.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.step = cls.env["product.config.step"].create({"name": "Shape step"})
        cls.attribute = cls.env["product.attribute"].create(
            {"name": "Kind cond", "create_variant": "no_variant"}
        )
        cls.classic, cls.cine = cls.env["product.attribute.value"].create([
            {"name": "Classic", "attribute_id": cls.attribute.id},
            {"name": "Ciné", "attribute_id": cls.attribute.id},
        ])
        cls.template = cls.env["product.template"].create({
            "name": "Panel cond", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": cls.attribute.id,
                "value_ids": [(6, 0, (cls.classic + cls.cine).ids)],
            })],
        })
        cls.line = cls.template.attribute_line_ids

    def test_01_opening_an_ATTRIBUTE_condition_creates_it_if_needed(self):
        """⚠️ La condition EST le lien : on ne peut pas ouvrir ce qui n'existe pas."""
        self.assertFalse(self.line.visibility_domain_id)
        action = self.template.configurator_open_condition(self.line.id)
        self.assertEqual(action["res_model"], "product.config.domain")
        self.assertEqual(action["target"], "new")
        self.assertTrue(self.line.visibility_domain_id)
        self.assertEqual(action["res_id"], self.line.visibility_domain_id.id)

    def test_02_and_reopens_the_SAME_one_afterwards(self):
        """Sinon chaque clic laisserait une condition de plus derrière lui."""
        premiere = self.template.configurator_open_condition(self.line.id)["res_id"]
        seconde = self.template.configurator_open_condition(self.line.id)["res_id"]
        self.assertEqual(premiere, seconde)

    def test_03_opening_a_VALUE_condition_creates_the_RULE_too(self):
        """⚠️ C'est ce que « Configuration Restrictions » faisait, et rien d'autre.

        Une condition par valeur demande un `product.config.line` — attribut,
        valeurs, condition. L'arbre l'affichait sans pouvoir en créer.
        """
        self.assertFalse(self.template.config_line_ids)
        action = self.template.configurator_open_condition(self.line.id, self.cine.id)
        self.assertEqual(len(self.template.config_line_ids), 1)
        regle = self.template.config_line_ids
        self.assertEqual(regle.value_ids, self.cine)
        self.assertEqual(action["res_id"], regle.domain_id.id)

    def test_04_and_it_does_not_touch_the_OTHER_value(self):
        self.template.configurator_open_condition(self.line.id, self.cine.id)
        rows = self.template.get_configurator_tree()
        valeurs = {v["name"]: v for v in rows[0]["values"]}
        self.assertFalse(valeurs["Classic"]["facets"])

    def test_05_opening_a_STEP_gives_its_settings(self):
        """⚠️ « Configuration Steps » portait AUSSI la condition de visibilité.

        L'ordre et l'appartenance sont déduits depuis D-202 — c'est cela qui
        avait cessé de servir, pas le reste.
        """
        self.line.config_step_id = self.step
        action = self.template.configurator_open_step(self.line.id)
        self.assertEqual(action["res_model"], "product.config.step.line")
        self.assertEqual(action["target"], "new")

    def test_06_and_says_nothing_when_the_row_opens_no_step(self):
        self.assertFalse(self.template.configurator_open_step(self.line.id))
