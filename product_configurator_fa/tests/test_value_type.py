from odoo.addons.base.tests.common import BaseCommon
import importlib.util
import os

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

    # ── ce que le FORMAT contraint à son tour ───────────────────────────────
    def test_10_only_three_formats_are_offered(self):
        """⚠️ Le catalogue hérité en proposait huit — Gerry n'en garde que trois.

        Un format dit comment se LIT un libellé : un mot, un entier, un décimal.
        Les cinq autres décrivaient des widgets de saisie (`text` n'est qu'un
        `char` plus haut, `binary` est un document, `color` fait double emploi
        avec le type « matière »).
        """
        offerts = dict(self.Attribute._fields["custom_type"].selection)
        self.assertEqual(sorted(offerts), ["char", "float", "integer"])

    def test_11_a_unit_qualifies_a_NUMBER(self):
        """« Chêne mm » n'est pas une lecture, c'est un accident de saisie."""
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.Attribute.create({
                "name": "Species measured", "create_variant": "no_variant",
                "custom_type": "char",
                "uom_id": self.env.ref("uom.product_uom_millimeter").id,
            })

    def test_12_nor_does_a_unit_stand_ALONE(self):
        """⚠️ Sans format du tout, l'unité ne qualifie rien non plus.

        Le piège serait d'écrire la garde sur les seuls formats textuels et de
        laisser passer le format vide, qui est le cas par DÉFAUT — donc le plus
        fréquent.
        """
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.Attribute.create({
                "name": "Nothing measured", "create_variant": "no_variant",
                "uom_id": self.env.ref("uom.product_uom_millimeter").id,
            })

    def test_13_the_numeric_formats_keep_their_unit(self):
        for fmt in ("integer", "float"):
            attr = self.Attribute.create({
                "name": f"Thickness {fmt}", "create_variant": "no_variant",
                "custom_type": fmt,
                "uom_id": self.env.ref("uom.product_uom_millimeter").id,
            })
            self.assertTrue(attr.uom_id)

    def test_14_leaving_the_numeric_formats_CLEARS_the_unit(self):
        """La vue masque l'unité dès que le format cesse d'être numérique.

        ⚠️ Éprouvé par `Form`, seul chemin où un onchange existe ([[L-157]]).
        """
        attr = self.Attribute.create({
            "name": "Was measured", "create_variant": "no_variant",
            "custom_type": "integer",
            "uom_id": self.env.ref("uom.product_uom_millimeter").id,
        })
        with Form(attr) as f:
            f.custom_type = "char"
        self.assertFalse(attr.uom_id)

    def test_15_the_migration_CLEANS_what_the_selection_no_longer_accepts(self):
        """⚠️ Une valeur retirée d'un `Selection` ne disparaît pas de la BASE.

        La colonne reste un `varchar`. Une ligne en `color` s'afficherait vide,
        s'effacerait au premier enregistrement, et une unité restée derrière
        rendrait l'attribut inenregistrable sur un champ devenu invisible.

        ⚠️ Ce test CHARGE LE FICHIER LIVRÉ et appelle son `migrate`. Recopier son
        SQL ici n'éprouverait que la copie : la migration pourrait être vide, mal
        nommée ou absente du paquet, et le test resterait vert.
        """
        chemin = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "migrations", "18.0.1.7.0", "post-migration.py",
        )
        self.assertTrue(os.path.exists(chemin), "la migration livrée est introuvable")
        spec = importlib.util.spec_from_file_location("_pcfa_migration", chemin)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        attr = self.Attribute.create({
            "name": "Legacy colour", "create_variant": "no_variant",
        })
        # Le format abandonné ne peut plus s'écrire par l'ORM — c'est tout l'objet
        # de la migration. On le pose donc comme la base le porte : en SQL.
        self.env.cr.execute(
            "UPDATE product_attribute SET custom_type = 'color', uom_id = %s "
            "WHERE id = %s",
            (self.env.ref("uom.product_uom_millimeter").id, attr.id),
        )

        migration.migrate(self.env.cr, "18.0.1.6.0")

        attr.invalidate_recordset()
        self.assertFalse(attr.custom_type)
        self.assertFalse(attr.uom_id)

    # ── ce que la VALEUR peut désigner (D-196) ──────────────────────────────
    def test_16_a_value_points_at_a_product_ONLY_when_the_type_says_so(self):
        """⚠️ `product_id` existait et n'était sur aucun écran.

        Il est pourtant lu à l'exécution — le prix du produit pointé remplace le
        supplément. La colonne le rend saisissable ; cette garde l'empêche de
        contredire le type de l'attribut.
        """
        from odoo.exceptions import ValidationError
        produit = self.env["product.product"].create({"name": "Bracket"})
        plain = self.Attribute.create({
            "name": "Plain list", "create_variant": "no_variant",
            "value_type": "value",
        })
        with self.assertRaises(ValidationError):
            self.env["product.attribute.value"].create({
                "name": "Bracket value", "attribute_id": plain.id,
                "product_id": produit.id,
            })

        pointing = self.Attribute.create({
            "name": "Bracket choice", "create_variant": "no_variant",
            "value_type": "product",
        })
        value = self.env["product.attribute.value"].create({
            "name": "Bracket value", "attribute_id": pointing.id,
            "product_id": produit.id,
        })
        self.assertEqual(value.product_id, produit)

    def test_17_the_value_image_RESIZES_again(self):
        """⚠️ Le fork avait remplacé le `Image` du core par un `Binary`.

        Sondé au runtime avant correction : plus de `max_width`, plus de contrôle
        de résolution — une photo de plusieurs méga-octets partait telle quelle
        dans une liste qui l'affiche en vignette, et un PDF déposé là passait.
        """
        champ = self.env["product.attribute.value"]._fields["image"]
        self.assertEqual(type(champ).__name__, "Image")
        self.assertEqual(champ.max_width, 256)
        self.assertEqual(champ.max_height, 256)
