"""Toute action rendue à un COMPOSANT doit être autosuffisante — L-165.

⚠️ Trouvé à l'écran par Gerry, pas par les tests : *« Cannot read properties of
undefined (reading 'map') »*. Une action déclenchée par un BOUTON passe par
`/web/dataset/call_button`, où le serveur la complète — `clean_action` déduit
`views` de `view_mode`. Rendue à un composant par un simple appel ORM, elle n'est
complétée par **personne**, et le client fait `action.views.map(...)`.

ⓘ Cette garde est une COUTURE entre deux mondes : rien, côté Python, ne dit
qu'une action partira vers un composant plutôt que vers un bouton.
"""

from odoo.addons.base.tests.common import BaseCommon


class ActionsAreComplete(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.step = cls.env["product.config.step"].create({"name": "Step act"})
        cls.attribute = cls.env["product.attribute"].create(
            {"name": "Kind act", "create_variant": "no_variant"}
        )
        cls.value = cls.env["product.attribute.value"].create(
            {"name": "Classic", "attribute_id": cls.attribute.id}
        )
        cls.template = cls.env["product.template"].create({
            "name": "Panel act", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": cls.attribute.id,
                "value_ids": [(6, 0, cls.value.ids)],
            })],
        })
        cls.line = cls.template.attribute_line_ids
        cls.line.config_step_id = cls.step
        cls.filtre = cls.env["product.attribute"].create({
            "name": "Handle act", "create_variant": "no_variant",
            "value_type": "product",
            "product_filter_domain": "[('type', '=', 'consu')]",
        })

    def _actions(self):
        """Toutes celles que l'arbre ou la fiche d'attribut appellent par l'ORM."""
        return {
            "values": self.line.action_open_values(),
            "réglages de la ligne": self.line.action_open_configurator_line(),
            "condition (attribut)": self.template.configurator_open_condition(
                self.line.id
            ),
            "condition (valeur)": self.template.configurator_open_condition(
                self.line.id, self.value.id
            ),
            "étape": self.template.configurator_open_step(self.line.id),
            "ajouter un attribut": self.template.action_configurator_add_attribute(),
            "ajouter une étape": self.template.action_configurator_add_step(),
            "valeurs du filtre": self.filtre.action_open_proposed_values(),
        }

    def test_01_every_action_carries_its_VIEWS(self):
        """⚠️ Sans `views`, l'écran lève une erreur au lieu d'ouvrir la fenêtre."""
        for nom, action in self._actions().items():
            self.assertTrue(action, f"{nom} ne rend aucune action")
            self.assertIn("views", action, f"{nom} n'a pas de `views`")
            self.assertTrue(action["views"], f"{nom} a des `views` vides")

    def test_02_and_the_view_matches_the_declared_mode(self):
        """Une action « form » qui porterait une vue liste ouvrirait la mauvaise."""
        for nom, action in self._actions().items():
            genres = {genre for _identifiant, genre in action["views"]}
            self.assertEqual(
                genres, {action["view_mode"]},
                f"{nom} : `views` et `view_mode` se contredisent",
            )

    def test_03_a_named_view_is_resolved_to_its_ID(self):
        """⚠️ `form_view_ref` en CONTEXTE ne suffit pas hors `call_button`.

        Il est lu quand le serveur compose les vues — ce qu'il ne fait pas ici.
        La vue doit donc être désignée par son identifiant.
        """
        action = self.template.configurator_open_condition(self.line.id)
        identifiant = action["views"][0][0]
        self.assertTrue(identifiant, "la vue de condition n'est pas résolue")
        self.assertEqual(
            identifiant,
            self.env.ref(
                "product_configurator_fa.product_configurator_condition_form_view"
            ).id,
        )


class PriceGridPlacement(BaseCommon):
    """La grille se range avec la liste de prix — D-214.

    ⚠️ Elles ne décident pas la même chose : la grille **produit** le prix d'un
    produit dimensionné, la liste de prix **l'ajuste**. Mais elles répondent à la
    même question — *« où se règle le prix ? »* — et deux portes éloignées pour
    une seule question, c'est une porte de trop.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = cls.env["product.template"].create(
            {"name": "Dimensioned", "config_ok": True}
        )

    def test_01_the_button_opens_the_grids_of_THIS_product(self):
        """⚠️ Les grilles sont par produit : sans domaine, on verrait celles de
        tout le catalogue, et on éditerait la mauvaise."""
        autre = self.env["product.template"].create(
            {"name": "Another one", "config_ok": True}
        )
        grille = self.env["product.price.grid"].create(
            {"name": "2026", "product_tmpl_id": self.template.id}
        )
        self.env["product.price.grid"].create(
            {"name": "2026", "product_tmpl_id": autre.id}
        )
        action = self.template.action_open_price_grids()
        trouvees = self.env["product.price.grid"].search(action["domain"])
        self.assertEqual(trouvees, grille)

    def test_02_and_it_carries_its_views(self):
        """Même exigence que partout : une action autosuffisante (L-165)."""
        action = self.template.action_open_price_grids()
        self.assertTrue(action.get("views"))
        self.assertEqual(
            [genre for _identifiant, genre in action["views"]], ["list", "form"]
        )

    def test_03_the_count_says_how_many_there_are(self):
        self.assertEqual(self.template.price_grid_count, 0)
        self.env["product.price.grid"].create(
            {"name": "2027", "product_tmpl_id": self.template.id}
        )
        self.template.invalidate_recordset()
        self.assertEqual(self.template.price_grid_count, 1)

    def test_04_the_configurator_tab_keeps_ONLY_the_tree(self):
        """⚠️ C'est la maquette : l'onglet ne montre plus que l'arbre.

        La grille en est partie pour le bouton d'en-tête, les restrictions et les
        étapes pour l'arbre lui-même (D-213), les images et le nom de variante
        pour un onglet à part.
        """
        import re

        arch = self.env["product.template"].get_view(view_type="form")["arch"]
        debut = arch.index('name="configurator"')
        fin = arch.index("</page>", debut)
        onglet = arch[debut:fin]
        for absent in ("price_grid_ids", "config_line_ids",
                       "config_step_line_ids", "config_image_ids"):
            self.assertNotIn(
                f'name="{absent}"', onglet,
                f"{absent} est encore dans l'onglet configurateur",
            )
        self.assertIn('name="configurator_line_ids"', onglet)
