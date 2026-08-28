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
    def test_10_only_four_formats_are_offered(self):
        """⚠️ Le catalogue hérité en proposait huit — il en reste quatre.

        Un format dit comment se LIT un libellé : un mot, un entier, un décimal.
        Les quatre retirés décrivaient des widgets de saisie (`text` n'est qu'un
        `char` plus haut, `date` n'a jamais désigné une caractéristique de
        produit, `color` fait double emploi avec le type « matière »).

        ⚠️ `binary` a été retiré puis RÉTABLI le même jour : je l'avais écarté
        d'un « une pièce jointe n'est pas une valeur », et c'était faux — le
        client joint un fichier comme valeur personnalisée, et sept tests du
        module l'exercent de bout en bout.
        """
        offerts = dict(self.Attribute._fields["custom_type"].selection)
        self.assertEqual(sorted(offerts), ["binary", "char", "float", "integer"])

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

    # ── un seul montant à la fois (D-197) ───────────────────────────────────
    def _column_conditions(self, model, sous):
        """Les conditions de masquage des colonnes, lues dans la vue ASSEMBLÉE."""
        import re
        arch = self.env[model].get_view(view_type="form")["arch"]
        arch = arch[arch.index(sous):]
        arch = arch[: arch.index("</list>")]
        conditions = {}
        for m in re.finditer(r'<field name="([a-z_0-9]+)"([^>]*)', arch):
            garde = re.search(r'column_invisible="([^"]*)"', m.group(2))
            conditions[m.group(1)] = garde.group(1) if garde else "False"
        return conditions

    def test_18_exactly_ONE_amount_shows_in_every_case(self):
        """⚠️ Ce n'est pas une question de place — c'est une question de FACTURE.

        Trois constats de Gerry se rejoignent ici :

          · *« default_extra_price ne peut pas être visible en même temps que
            default_extra_price_sqm »* — le module dit lui-même pourquoi : « Odoo
            somme `price_extra` partout, et y ranger 25 €/m² le ferait facturer
            25 € » ;
          · *« s'il est possible de modifier et que seul un produit de la liste a
            son prix modifié, ça peut être trompeur et fausser les prix »* — d'où
            le prix du produit, en lecture, à la place du montant saisissable ;
          · *« pour un produit, seule la ligne de plus-value unitaire remplacée
            par le prix du produit est visible ; c'est uniquement la matière qui
            peut appliquer un prix au mètre carré ou unitaire »*.

        ⓘ Les trois se résument en un invariant : quels que soient le type de
        valeur et le mode de prix, **un montant et un seul** est à l'écran. La
        garde l'éprouve sur les six combinaisons, en ÉVALUANT les conditions de
        la vue assemblée — comparer des chaînes recopiées rougirait à la moindre
        reformulation sans rien dire de la règle.
        """
        conditions = self._column_conditions("product.attribute", 'name="value_ids"')

        class _Parent:
            def __init__(self, value_type, price_mode):
                self.value_type = value_type
                self.price_mode = price_mode

        montants = ("default_extra_price", "product_price", "default_extra_price_sqm")
        for value_type in ("value", "product", "material"):
            for price_mode in ("fixed", "per_sqm"):
                parent = _Parent(value_type, price_mode)
                visibles = [
                    nom for nom in montants
                    if not eval(  # noqa: S307
                        conditions[nom], {"__builtins__": {}}, {"parent": parent}
                    )
                ]
                self.assertEqual(
                    len(visibles), 1,
                    f"{value_type}/{price_mode} : {visibles or 'aucun montant'}",
                )

    def test_19_and_the_amounts_sit_at_the_END_of_the_line(self):
        """« c'est l'un ou l'autre EN FIN DE LIGNE ».

        ⚠️ La colonne au m² était insérée juste après le nom, donc loin de son
        alternative : les deux montants se lisaient à deux endroits différents de
        la ligne selon le mode.
        """
        conditions = self._column_conditions("product.attribute", 'name="value_ids"')
        # ⓘ On ne compte que les colonnes qu'un utilisateur peut voir : la devise
        # est portée en `column_invisible="True"` pour que `widget="monetary"` ait
        # de quoi s'afficher, et elle n'occupe aucune place à l'écran.
        ordre = [n for n in conditions if conditions[n] != "True"]
        montants = ["default_extra_price", "product_price", "default_extra_price_sqm"]
        places = [ordre.index(n) for n in montants]
        self.assertEqual(
            places, sorted(places),
            "les montants ne se suivent plus dans l'ordre attendu",
        )
        self.assertEqual(
            places[-1] - places[0], len(montants) - 1,
            "une colonne étrangère s'est glissée entre les montants",
        )
        # Après eux, plus aucune colonne que l'utilisateur puisse voir.
        apres = [n for n in ordre[places[-1] + 1:] if conditions[n] != "True"]
        self.assertEqual(apres, [], f"des colonnes suivent encore : {apres}")

    # ── la ligne se remplit seule (D-198) ───────────────────────────────────
    def test_20_picking_a_product_FILLS_the_name(self):
        """⚠️ `name` est REQUIS, et rien ne le recopiait.

        Attente de Gerry : « lors du clic, toute la ligne est pré-remplie ». La
        miniature suivait seule (elle est `related`) ; le nom, non — il fallait
        retaper à la main ce qu'on venait de désigner, sous peine de ne pas
        pouvoir enregistrer.
        """
        produit = self.env["product.product"].create({"name": "Stainless bracket"})
        attribute = self.Attribute.create({
            "name": "Bracket", "create_variant": "no_variant",
            "value_type": "product",
        })
        with Form(self.env["product.attribute.value"].with_context(
                default_attribute_id=attribute.id)) as f:
            f.product_id = produit
            self.assertEqual(f.name, produit.display_name)

    def test_21_but_a_name_CHOSEN_BY_HAND_is_never_overwritten(self):
        """⚠️ Un libellé est ce que le CLIENT lit — il ne s'écrase pas seul.

        Sans cette précaution, corriger le produit d'une valeur renommée
        effacerait le libellé choisi, en silence.
        """
        premier = self.env["product.product"].create({"name": "Bracket A"})
        second = self.env["product.product"].create({"name": "Bracket B"})
        attribute = self.Attribute.create({
            "name": "Bracket choice", "create_variant": "no_variant",
            "value_type": "product",
        })
        value = self.env["product.attribute.value"].create({
            "name": "Renfort renforcé", "attribute_id": attribute.id,
            "product_id": premier.id,
        })
        with Form(value) as f:
            f.product_id = second
        self.assertEqual(value.name, "Renfort renforcé")

    def test_22_and_a_name_INHERITED_from_the_previous_product_follows(self):
        """Le pendant : ce qui venait du produit suit le produit."""
        premier = self.env["product.product"].create({"name": "Bracket A"})
        second = self.env["product.product"].create({"name": "Bracket B"})
        attribute = self.Attribute.create({
            "name": "Bracket followed", "create_variant": "no_variant",
            "value_type": "product",
        })
        value = self.env["product.attribute.value"].create({
            "name": premier.display_name, "attribute_id": attribute.id,
            "product_id": premier.id,
        })
        with Form(value) as f:
            f.product_id = second
        self.assertEqual(value.name, second.display_name)

    def test_23_an_ATTACHMENT_is_not_a_reading_format(self):
        """⚠️ `binary` échappe à la règle des formats, et pour une bonne raison.

        Le raisonnement de la garde est : « quand la valeur désigne un produit,
        l'objet EST la réponse, il n'y a pas de libellé à lire ». Une pièce
        jointe n'est pas un libellé — c'est un fichier que le client envoie en
        PLUS. Rien n'empêche de demander un plan ou un échantillon à côté d'un
        produit désigné.

        ⓘ Trouvé en essayant de faire entrer trois tests du module dans la garde.
        """
        attribute = self.Attribute.create({
            "name": "Bracket with a drawing", "create_variant": "no_variant",
            "value_type": "product", "custom_type": "binary",
        })
        self.assertEqual(attribute.custom_type, "binary")

    def test_24_but_a_unit_still_has_nothing_to_qualify_there(self):
        """L'exemption porte sur le FORMAT, pas sur l'unité."""
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.Attribute.create({
                "name": "Bracket measured", "create_variant": "no_variant",
                "value_type": "product", "custom_type": "binary",
                "uom_id": self.env.ref("uom.product_uom_millimeter").id,
            })
