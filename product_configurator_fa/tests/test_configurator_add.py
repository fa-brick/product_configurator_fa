"""Poser une étape depuis l'arbre — 2026-08-29, en remplacement de D-212.

⚠️ **LE DIALOGUE A DISPARU, PAS LA CONTRAINTE.** Gerry : *« quand on ajoute une
étape, le comportement doit être identique à ajouter une section : une ligne se
crée, on la nomme, puis on la déplace à sa position »*. C'est le geste des lignes
de commande — on ne choisit plus À L'AVANCE une chose qu'on saura mieux en la
voyant.

⚠️ Mais une étape reste un MARQUEUR porté par la ligne qui l'ouvre (D-202) : elle
ne peut pas se poser « en bas » comme une section, faute de ligne sous la
dernière. Elle se pose donc sur la dernière ligne LIBRE, et le glisser fait le
reste.
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
        cls.second = cls.env["product.attribute"].create(
            {"name": "Second add", "create_variant": "no_variant"}
        )
        cls.gloss = cls.env["product.attribute.value"].create(
            {"name": "Gloss", "attribute_id": cls.second.id}
        )
        cls.empty = cls.env["product.template"].create(
            {"name": "Empty product", "config_ok": True}
        )
        cls.filled = cls.env["product.template"].create({
            "name": "Filled product", "config_ok": True,
            "attribute_line_ids": [
                (0, 0, {"attribute_id": cls.attribute.id,
                        "value_ids": [(6, 0, cls.value.ids)], "sequence": 10}),
                (0, 0, {"attribute_id": cls.second.id,
                        "value_ids": [(6, 0, cls.gloss.ids)], "sequence": 20}),
            ],
        })

    def _line(self, attribute):
        return self.filled.attribute_line_ids.filtered(
            lambda ligne, a=attribute: ligne.attribute_id == a
        )

    # ─ AJOUTER ──────────────────────────────────────────────────────────────

    def test_01_adding_a_step_needs_NO_dialog_and_marks_the_last_free_line(self):
        """ⓘ La dernière libre, en remontant : c'est le plus bas qu'un marqueur
        puisse aller, donc l'équivalent du « en bas » d'une section."""
        step_id = self.filled.configurator_add_step()
        self.assertTrue(step_id, "aucune étape créée")
        self.assertEqual(self._line(self.second).config_step_id.id, step_id)
        self.assertFalse(self._line(self.attribute).config_step_id)

    def test_02_and_it_renders_a_BAND_the_tree_can_name(self):
        self.filled.configurator_add_step()
        genres = [r["kind"] for r in self.filled.get_configurator_tree()]
        self.assertEqual(genres, ["attribute", "step", "attribute"])

    def test_03_a_step_is_NEW_every_time_so_renaming_hurts_nobody(self):
        """⚠️ Jamais une étape du catalogue réemployée : c'est ce qui rend le
        renommage sans conséquence pour les autres produits."""
        premier = self.filled.configurator_add_step()
        self._line(self.second).config_step_id = False
        second = self.filled.configurator_add_step()
        self.assertNotEqual(premier, second)

    def test_04_adding_a_step_on_an_EMPTY_product_explains_why_it_cannot(self):
        """⚠️ C'est la contrepartie de la forme (A) : une étape ne flotte pas.

        Elle s'ouvre SUR un attribut. Sans attribut, il n'y a rien à ouvrir — et
        il vaut mieux le dire que rendre un bouton inerte.
        """
        with self.assertRaises(UserError):
            self.empty.configurator_add_step()

    def test_05_and_when_EVERY_line_already_opens_a_step_it_says_so(self):
        """⚠️ Sans cette garde, le marqueur neuf écraserait une étape existante —
        silencieusement, et sans que rien ne l'ait demandé."""
        self._line(self.attribute).config_step_id = self.step
        self.filled.configurator_add_step()
        with self.assertRaises(UserError):
            self.filled.configurator_add_step()

    # ─ NOMMER ───────────────────────────────────────────────────────────────

    def test_06_naming_the_band_names_the_step(self):
        step_id = self.filled.configurator_add_step()
        self.filled.configurator_rename_step(step_id, "  Dimensions  ")
        self.assertEqual(
            self.env["product.config.step"].browse(step_id).name, "Dimensions"
        )

    def test_07_an_EMPTY_name_is_ignored_rather_than_written(self):
        """ⓘ `name` est obligatoire : un nom vidé ne s'écrit pas, il s'ignore.
        Le bandeau garde le sien, et rien ne se perd."""
        step_id = self.filled.configurator_add_step()
        avant = self.env["product.config.step"].browse(step_id).name
        self.assertFalse(self.filled.configurator_rename_step(step_id, "   "))
        self.assertEqual(
            self.env["product.config.step"].browse(step_id).name, avant
        )

    def test_08_a_step_this_product_does_NOT_declare_cannot_be_renamed(self):
        """⚠️ Sans cette garde, l'arbre d'un produit renommerait n'importe quelle
        étape du catalogue."""
        with self.assertRaises(UserError):
            self.filled.configurator_rename_step(self.step.id, "Hijacked")

    # ─ DÉPLACER ─────────────────────────────────────────────────────────────

    def test_09_moving_the_band_moves_the_MARKER_not_a_line(self):
        """⚠️ L'étape n'a pas de rang à elle : son rang est celui de la ligne qui
        l'ouvre (D-202)."""
        step_id = self.filled.configurator_add_step()
        self.filled.configurator_move_step(step_id, self._line(self.attribute).id)
        self.assertEqual(self._line(self.attribute).config_step_id.id, step_id)
        self.assertFalse(self._line(self.second).config_step_id)
        genres = [r["kind"] for r in self.filled.get_configurator_tree()]
        self.assertEqual(genres, ["step", "attribute", "attribute"])

    def test_10_a_line_that_already_opens_ANOTHER_step_refuses_the_drop(self):
        """⚠️ Une ligne n'ouvre qu'UNE étape : accepter écraserait l'autre."""
        self._line(self.attribute).config_step_id = self.step
        step_id = self.filled.configurator_add_step()
        with self.assertRaises(UserError):
            self.filled.configurator_move_step(
                step_id, self._line(self.attribute).id
            )

    def test_11_a_line_of_ANOTHER_product_is_refused(self):
        """⚠️ La seconde barrière, celle qui ne dépend pas de l'interface (D-080)
        — un import ou un script ne passe pas par l'écran."""
        autre = self.env["product.template"].create({
            "name": "Other product", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": self.attribute.id,
                "value_ids": [(6, 0, self.value.ids)],
            })],
        })
        step_id = self.filled.configurator_add_step()
        with self.assertRaises(UserError):
            self.filled.configurator_move_step(
                step_id, autre.attribute_line_ids.id
            )

    def test_12_the_gestures_are_usable_by_a_MANAGER_not_only_by_admin(self):
        """⚠️ Ces coutures s'exécutent SOUS un utilisateur réel — c'est tout leur
        objet. L'assistant retiré portait sa propre règle d'accès ([[L-169]]) ;
        les méthodes qui le remplacent écrivent sur des modèles ordinaires, et
        c'est CETTE chaîne de droits qu'il faut éprouver."""
        gestionnaire = self.env["res.users"].create({
            "name": "Config manager",
            "login": "cfg_manager_acl",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("product.group_product_manager").id,
                self.env.ref(
                    "product_configurator_fa"
                    ".group_product_configurator_fa_manager"
                ).id,
            ])],
        })
        produit = self.filled.with_user(gestionnaire)
        step_id = produit.configurator_add_step()
        produit.configurator_rename_step(step_id, "Dimensions")
        produit.configurator_move_step(
            step_id,
            produit.attribute_line_ids.sorted()[0].id,
        )
        self.assertEqual(
            produit.attribute_line_ids.sorted()[0].config_step_id.id, step_id
        )
