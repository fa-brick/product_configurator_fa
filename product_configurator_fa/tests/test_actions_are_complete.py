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
            "condition (attribut)": self.template.configurator_open_condition(
                self.line.id
            ),
            "condition (valeur)": self.template.configurator_open_condition(
                self.line.id, self.value.id
            ),
            "étape": self.template.configurator_open_step(self.line.id),
            "ajouter un attribut": self.template.action_configurator_add_attribute(),
            "ajouter une étape": self.template.action_configurator_add_step(),
            "produits du filtre": self.filtre.action_open_proposed_products(),
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
                "product_configurator_fa.product_config_domain_form_view_template"
            ).id,
        )
