"""La corbeille a DEUX visages — B4, QC, D-205.

⚠️ *« Si aucun variant n'a été créé on peut supprimer ; s'il y a déjà eu des
variants on désactive. »* Le cœur le fait déjà — `unlink()` archive ce qu'il ne
peut pas supprimer. Ce lot n'ajoute aucun comportement : il rend l'état
**visible avant le clic**, sans quoi le même geste détruit ici et masque là.
"""

from unittest.mock import patch

from odoo.addons.base.tests.common import BaseCommon


class RemovalEffect(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create(
            {"name": "Finish R", "create_variant": "always"}
        )
        cls.matt, cls.gloss = cls.env["product.attribute.value"].create([
            {"name": "Matt", "attribute_id": cls.attribute.id},
            {"name": "Gloss", "attribute_id": cls.attribute.id},
        ])
        cls.template = cls.env["product.template"].create({
            "name": "Panel R",
            "attribute_line_ids": [(0, 0, {
                "attribute_id": cls.attribute.id,
                "value_ids": [(6, 0, (cls.matt + cls.gloss).ids)],
            })],
        })
        cls.line = cls.template.attribute_line_ids


    def test_01_an_UNUSED_value_would_be_deleted(self):
        """Le cas ordinaire : rien ne retient la valeur."""
        for ptav in self.line.product_template_value_ids:
            self.assertEqual(ptav.removal_effect, "delete")

    def _rien_de_supprimable(self):
        """Simule un point d'extension qui retient TOUTES les variantes.

        ⚠️ On ne fabrique pas le blocage avec une commande ni un mouvement : ce
        module ne dépend ni de `sale` ni de `stock`, et un test qui les
        emprunterait casserait là où ils manquent. Ce qui est éprouvé ici est
        NOTRE décision — interroger le point d'extension et le croire —, pas la
        façon dont `sale` ou `stock` retiennent une variante.
        """
        Product = type(self.env["product.product"])
        return patch.object(Product, "_filter_to_unlink", lambda self: self.browse())

    def test_02_a_value_whose_variant_CANNOT_go_would_be_deactivated(self):
        """⚠️ Ce n'est pas « utilisée » qui bloque, c'est « indestructible ».

        Une variante sans commande ni mouvement s'en va avec la valeur. D'où
        l'appel à `_filter_to_unlink`, le point d'extension où `sale` écarte ce
        qui est commandé et `stock` ce qui a bougé — plutôt qu'un comptage de
        variantes, qui dirait « archiver » pour tout produit à variantes.
        """
        ptav = self.line.product_template_value_ids[0]
        self.assertTrue(ptav.ptav_product_variant_ids, "aucune variante produite")
        with self._rien_de_supprimable():
            ptav.invalidate_recordset()
            self.assertEqual(ptav.removal_effect, "archive")

    def _en_cours_de_saisie(self, valeurs):
        """La ligne telle qu'elle est À L'ÉCRAN, avant enregistrement.

        ⚠️ Un `onchange` compare ce qui est saisi à `_origin`, l'enregistrement
        en base. Écrire `ligne.value_ids -= v` sur un enregistrement RÉEL écrit
        d'abord : `_origin` a déjà changé, plus rien n'a été « retiré », et
        l'avertissement ne peut plus se lever. Même piège qu'en [[L-157]].
        """
        return self.line.new({"value_ids": [(6, 0, valeurs.ids)]}, origin=self.line)

    def test_03_removing_it_WARNS_before_the_save(self):
        """⚠️ L'écart ne se voit qu'après coup : la valeur reste là, grisée."""
        ptav = self.line.product_template_value_ids[0]
        retiree = ptav.product_attribute_value_id
        en_cours = self._en_cours_de_saisie(self.line.value_ids - retiree)
        with self._rien_de_supprimable():
            avertissement = en_cours._onchange_values_warns_about_deactivation()
        self.assertTrue(avertissement, "aucun avertissement sur un retrait bloqué")
        self.assertIn(retiree.name, avertissement["warning"]["message"])

    def test_04_and_says_NOTHING_when_the_value_can_simply_go(self):
        """Avertir toujours serait un bruit — et ferait douter du cas qui compte."""
        en_cours = self._en_cours_de_saisie(self.line.value_ids - self.gloss)
        self.assertFalse(en_cours._onchange_values_warns_about_deactivation())

    def test_05_nor_when_nothing_is_REMOVED(self):
        """⚠️ Un `onchange` se déclenche aussi quand on AJOUTE une valeur.

        Sans ce sens-là, on avertirait au moment d'enrichir la liste — quand rien
        ne disparaît.
        """
        troisieme = self.env["product.attribute.value"].create(
            {"name": "Satin", "attribute_id": self.attribute.id}
        )
        en_cours = self._en_cours_de_saisie(self.line.value_ids + troisieme)
        with self._rien_de_supprimable():
            self.assertFalse(en_cours._onchange_values_warns_about_deactivation())
