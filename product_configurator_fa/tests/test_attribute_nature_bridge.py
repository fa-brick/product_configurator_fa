# -*- coding: utf-8 -*-
"""`custom_type` cède la source de vérité à `nature`, sans que rien s'en aperçoive.

⚠️ **Ce qui est éprouvé ici n'est pas la nature — c'est le PONT.** La nature vit dans
`product_attribute_advanced` et y a ses propres tests. Ce fichier tient la seule chose qui
puisse casser ici : les **47 points d'appel** de `custom_type`, lectures et écritures
confondues, doivent continuer de fonctionner sans être touchés. Un seul aller-retour qui
ne tomberait pas juste, et un test hérité d'OCA se met à écrire un format que la nature
contredit au recalcul suivant.
"""
from odoo.addons.base.tests.common import BaseCommon


class TestAttributeNatureBridge(BaseCommon):

    def _attribute(self, **kw):
        vals = {"name": "Question %s" % self.env["product.attribute"].search_count([])}
        vals.update(kw)
        return self.env["product.attribute"].create(vals)

    # ── écrire le FORMAT écrit la nature ────────────────────────────────

    def test_writing_a_format_at_CREATE_sets_the_nature(self):
        """C'est la forme qu'emploient les tests hérités : créer avec un format."""
        self.assertEqual(self._attribute(custom_type="integer").nature, "number")
        self.assertEqual(self._attribute(custom_type="float").nature, "number")
        self.assertEqual(self._attribute(custom_type="char").nature, "text")

    def test_writing_a_format_LATER_sets_the_nature_too(self):
        attribute = self._attribute()
        attribute.custom_type = "float"
        self.assertEqual(attribute.nature, "number")

    def test_BINARY_becomes_an_ATTACHMENT(self):
        """⚠️ La ligne qui a failli manquer : la mesure disait qu'aucune donnée ne porte
        ce format, mais le CODE s'en sert — un client téléverse un fichier comme réponse.
        Sans elle, adosser le format à la nature aurait supprimé la fonction en silence.
        """
        self.assertEqual(self._attribute(custom_type="binary").nature, "attachment")

    # ── écrire la NATURE écrit le format ────────────────────────────────

    def test_a_NUMBER_gets_the_most_general_format(self):
        """`float` plutôt qu'`integer` : le format qui ne perd pas de décimale."""
        self.assertEqual(self._attribute(nature="number").custom_type, "float")

    def test_an_ATTACHMENT_gets_the_binary_format(self):
        self.assertEqual(self._attribute(nature="attachment").custom_type, "binary")

    def test_a_PRODUCT_and_a_MATERIAL_are_answered_by_a_discrete_value(self):
        """Leur réponse est une valeur choisie ; c'est la NATURE qui dit ce qu'elle
        désigne, pas le format de saisie."""
        self.assertEqual(self._attribute(nature="product").custom_type, "char")
        self.assertEqual(self._attribute(nature="material").custom_type, "char")

    # ── ce que le pont ne doit PAS écraser ──────────────────────────────

    def test_an_INTEGER_survives_under_a_NUMBER(self):
        """⚠️ Le cœur du pont. `integer` est une PRÉCISION que la nature ne porte pas :
        la recalculer en `float` l'effacerait à chaque enregistrement de la fiche — une
        perte silencieuse, et à chaque écriture.
        """
        attribute = self._attribute(custom_type="integer")
        self.assertEqual(attribute.nature, "number")
        attribute.name = "Renommée"        # une écriture qui ne touche pas au format
        self.assertEqual(attribute.custom_type, "integer")

    def test_an_attribute_WITHOUT_a_format_keeps_none(self):
        """ⓘ « Aucun format » est l'état historique de la plupart des attributs, et `text`
        est leur nature par défaut : inventer un `char` là où il n'y en avait pas ne
        rendrait service à personne."""
        attribute = self._attribute()
        self.assertEqual(attribute.nature, "text")
        self.assertFalse(attribute.custom_type)

    def test_changing_the_nature_REWRITES_an_inconsistent_format(self):
        """Là, en revanche, il faut corriger : un `char` sous une nature `number` ne
        décrit plus rien."""
        attribute = self._attribute(custom_type="char")
        attribute.nature = "number"
        self.assertEqual(attribute.custom_type, "float")

    # ── ce qui a été DÉPLACÉ, et ne doit pas revenir ────────────────────

    def test_the_UNIT_now_comes_from_the_shared_module(self):
        """⚠️ Le fork le définissait ; le module partagé le porte désormais pour les
        deux. Le définir des deux côtés, c'est le doublon que tout ce chantier évite.
        """
        field = self.env["product.attribute"]._fields["uom_id"]
        self.assertEqual(field.comodel_name, "uom.uom")
        self.assertNotIn(
            "product_configurator_fa", getattr(field, "_modules", ()) or ())
