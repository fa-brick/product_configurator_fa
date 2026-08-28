"""Un attribut peut être MULTIPLE **et** autoriser l'ajout — D-220.

⚠️ Question de Gerry : *« si l'attribut autorise l'ajout, il ne peut pas être
multi ? »*. **Aucune contrainte de modèle ne l'interdisait** : deux `readonly`
croisés dans la vue, hérités du fork OCA, sans raison consignée.

ⓘ Et l'assistant prévoit explicitement la combinaison — `if field_type ==
"many2many": field_val = [(6, False, [custom_option_id])]`. Cette branche
n'existerait pas si les deux s'excluaient. Le verrou rendait donc inatteignable
un cas que le moteur sait traiter.

⚠️ Ces gardes existent parce qu'ouvrir une porte sur un chemin non éprouvé
n'ouvre rien : elles font passer un attribut multi-avec-ajout **dans l'assistant
lui-même**, pas seulement dans le modèle.
"""

from odoo.addons.base.tests.common import BaseCommon


class MultiAndCustom(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create({
            "name": "Finish multi", "create_variant": "no_variant",
            "custom_type": "char",
        })
        cls.values = cls.env["product.attribute.value"].create([
            {"name": "Matt", "attribute_id": cls.attribute.id},
            {"name": "Gloss", "attribute_id": cls.attribute.id},
        ])
        cls.template = cls.env["product.template"].create({
            "name": "Panel multi", "config_ok": True,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": cls.attribute.id,
                "value_ids": [(6, 0, cls.values.ids)],
                "multi": True,
                "custom": True,
            })],
        })
        cls.line = cls.template.attribute_line_ids

    def test_01_the_two_flags_COEXIST_in_the_model(self):
        """Rien ne les opposait : seule la vue le faisait."""
        self.assertTrue(self.line.multi)
        self.assertTrue(self.line.custom)

    def test_02_the_wizard_offers_a_MANY2MANY_for_such_a_line(self):
        """⚠️ C'est le type du champ qui décide du reste.

        `multi` rend le champ many2many ; c'est cette branche que le code de la
        saisie libre prévoit — et qui n'aurait aucun sens si les deux drapeaux
        s'excluaient.
        """
        # ⚠️ L'assistant n'injecte ses champs dynamiques QUE s'il se trouve
        # lui-même dans le contexte (`_find_wizard_context` lit `wizard_id`).
        # Sans cela, `fields_get` rend les champs ordinaires et la garde échoue
        # sur son propre montage, pas sur le code.
        wizard = self.env["product.configurator"].create(
            {"product_tmpl_id": self.template.id}
        )
        champs = wizard.with_context(wizard_id=wizard.id).fields_get()
        nom = f"{wizard._prefixes['field_prefix']}{self.attribute.id}"
        self.assertIn(nom, champs, "l'attribut n'est pas offert par l'assistant")
        self.assertEqual(champs[nom]["type"], "many2many")

    def test_03_and_the_CUSTOM_option_is_among_the_offered_values(self):
        """⚠️ Le cas ouvert doit être ATTEIGNABLE, pas seulement permis.

        La valeur « personnalisée » est une valeur d'attribut comme les autres,
        ajoutée à la liste proposée quand la ligne autorise l'ajout. Sans elle,
        cocher « Allow add » sur une ligne multiple ne donnerait aucun moyen
        d'ajouter — le verrou aurait été remplacé par un silence.
        """
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.template.id, "user_id": self.env.user.id,
        })
        custom = self.env["product.config.session"].get_custom_value_id()
        disponibles = session.values_available(
            check_val_ids=(self.values.ids + [custom.id])
        )
        self.assertIn(custom.id, disponibles)
