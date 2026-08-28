from odoo.addons.base.tests.common import BaseCommon
from odoo.tests.common import Form


class ValueType(BaseCommon):
    """Le TYPE d'un attribut — ce que ses valeurs DÉSIGNENT (A2, 2026-08-28).

    ⚠️ Trois notions vivaient empilées dans deux champs mal découpés, et c'est ce
    qui faisait dire à Gerry que *« le type des attributs n'est pas explicite »*.
    Elles sont désormais séparées, et ce fichier grave leur INDÉPENDANCE :

      · le TYPE          — ce que la valeur désigne (`value_type`) ;
      · le FORMAT        — comment elle se lit (`custom_type`) ;
      · l'AJOUT          — le client peut-il en créer une (`val_custom`).

    Une épaisseur est de type « valeur », de format « entier », et peut être
    ouverte ou fermée à l'ajout : les trois ne se déduisent pas l'une de l'autre.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attribute = cls.env["product.attribute"]

    def test_01_default_is_a_plain_value(self):
        """Sans rien dire, une valeur ne désigne qu'elle-même."""
        # C'est le cas de l'immense majorité des attributs existants : le défaut
        # ne doit donc rien changer pour eux.
        attr = self.Attribute.create({"name": "Finish", "create_variant": "no_variant"})
        self.assertEqual(attr.value_type, "value")

    def test_02_the_three_notions_are_independent(self):
        """⚠️ Le format et l'ajout ne se déduisent pas du type, ni l'un de l'autre."""
        # Une épaisseur ÉNUMÉRÉE — 10 / 15 / 18 — reste un nombre. C'est le trou
        # que la séparation ferme : `custom_type` décrivait jusqu'ici la saisie
        # libre, alors que la grille de prix et le moteur de géométrie lisent ces
        # valeurs comme des nombres, saisies ou non.
        epaisseur = self.Attribute.create({
            "name": "Thickness", "create_variant": "no_variant",
            "custom_type": "integer", "val_custom": False,
        })
        self.assertEqual(epaisseur.value_type, "value")
        self.assertEqual(epaisseur.custom_type, "integer")
        self.assertFalse(epaisseur.val_custom)

    def test_03_a_numeric_attribute_is_numeric_WITHOUT_free_entry(self):
        """⚠️ La preuve que le trou est bien dans la VUE, pas dans le modèle.

        `_is_numeric_custom` lit `custom_type` et lui seul : une épaisseur
        énumérée est donc déjà normalisée par le modèle. Ce que l'interface
        empêche, c'est de RENSEIGNER le format sans cocher la saisie libre —
        c'est le sujet de A3, et ce test dit que le modèle n'y est pour rien.
        """
        epaisseur = self.Attribute.create({
            "name": "Thickness enum", "create_variant": "no_variant",
            "custom_type": "float", "val_custom": False,
        })
        self.assertEqual(epaisseur.canonical_custom_value("18.0"), "18")
        self.assertEqual(epaisseur.canonical_custom_value(" 18,5 ".replace(",", ".")), "18.5")

    def test_04_a_product_typed_attribute(self):
        """Le second type : la valeur désigne un produit."""
        attr = self.Attribute.create({
            "name": "Handle", "create_variant": "no_variant", "value_type": "product",
        })
        self.assertEqual(attr.value_type, "product")

    def test_05_the_core_does_NOT_know_materials(self):
        """⚠️ « matière » appartient au module PONT, et le cœur l'ignore.

        Pas pour une raison de licence — D-075 autorise expressément le
        configurateur AGPL-3 à dépendre de l'éditeur LGPL-3 — mais de MODULARITÉ :
        un configurateur sans éditeur 3D doit continuer de fonctionner. Si ce test
        échoue, c'est que le type a migré dans le cœur, et cette garantie avec lui.
        """
        types = dict(self.Attribute._fields["value_type"].selection)
        self.assertIn("value", types)
        self.assertIn("product", types)
        if "material" in types:
            # Le pont est installé : il a le droit d'y être, mais il doit venir de
            # LUI. La liste déclarée par le cœur, elle, ne doit pas le contenir.
            self.assertNotIn(
                "material",
                dict(self.Attribute.VALUE_TYPES),
                "« matière » a été déclaré dans le cœur du configurateur",
            )

    # ── ce que le type CONTRAINT ────────────────────────────────────────────
    def test_06_a_format_makes_no_sense_on_a_product(self):
        """⚠️ Trois notions INDÉPENDANTES ne veulent pas dire aucune contrainte.

        Constat de Gerry : *« on peut choisir value type : product et format
        integer, ça n'a pas de sens »*. Un format dit comment LIRE un libellé ;
        quand la valeur désigne un produit, l'objet EST la réponse.
        """
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.Attribute.create({
                "name": "Handle typed", "create_variant": "no_variant",
                "value_type": "product", "custom_type": "integer",
            })

    def test_07_nor_does_a_unit(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.Attribute.create({
                "name": "Handle measured", "create_variant": "no_variant",
                "value_type": "product",
                "uom_id": self.env.ref("uom.product_uom_millimeter").id,
            })

    def test_08_switching_type_CLEARS_the_format(self):
        """⚠️ Sans ce nettoyage, le refus tomberait sur un champ devenu INVISIBLE.

        La vue masque format et unité hors du type « valeur ». Un format saisi
        avant la bascule resterait donc en base, invisible, et la contrainte
        refuserait l'enregistrement en désignant un champ que l'utilisateur ne
        voit plus — le pire des messages d'erreur.

        ⚠️ Éprouvé par `Form`, et pas autrement : écrire `value_type` directement
        sur l'enregistrement déclenche la contrainte AVANT tout onchange, et le
        test échouait alors sur son propre raccourci. `Form` joue les onchanges
        comme l'interface, donc il éprouve le chemin que l'utilisateur emprunte.
        """
        attr = self.Attribute.create({
            "name": "Was a number", "create_variant": "no_variant",
            "custom_type": "float",
            "uom_id": self.env.ref("uom.product_uom_millimeter").id,
        })
        with Form(attr) as f:
            f.value_type = "product"
        self.assertFalse(attr.custom_type)
        self.assertFalse(attr.uom_id)

    def test_09_the_plain_type_keeps_its_format(self):
        """Le cas courant n'est pas gêné : une épaisseur garde son format."""
        attr = self.Attribute.create({
            "name": "Thickness kept", "create_variant": "no_variant",
            "value_type": "value", "custom_type": "integer",
            "uom_id": self.env.ref("uom.product_uom_millimeter").id,
        })
        self.assertEqual(attr.custom_type, "integer")
