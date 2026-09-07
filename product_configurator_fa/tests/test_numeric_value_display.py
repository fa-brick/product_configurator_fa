from odoo.addons.base.tests.common import BaseCommon


class NumericValueDisplay(BaseCommon):
    """La valeur d'un attribut numérique est le NOMBRE ; l'affichage porte l'unité.

    Arbitrage de Gerry le 2026-08-22. OCA tenait déjà la règle à UN endroit — le
    libellé d'une valeur de session — et la perdait partout ailleurs.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_mm = cls.env.ref("uom.product_uom_millimeter")
        cls.attr_width = cls.env["product.attribute"].create(
            {
                "name": "Width",
                "val_custom": True,
                "custom_type": "float",
                "uom_id": cls.uom_mm.id,
                "create_variant": "no_variant",
            }
        )
        cls.attr_note = cls.env["product.attribute"].create(
            {
                "name": "Engraving",
                "val_custom": True,
                "custom_type": "char",
                "create_variant": "no_variant",
            }
        )
        cls.template = cls.env["product.template"].create(
            {"name": "Measured Door", "config_ok": True}
        )
        cls.line_width = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attr_width.id,
                "custom": True,
            }
        )
        cls.session = cls.env["product.config.session"].create(
            {"product_tmpl_id": cls.template.id, "user_id": cls.env.user.id}
        )

    # ── la valeur ────────────────────────────────────────────────────────────

    def test_01_canonical_form_of_a_number(self):
        """`2400`, `2400.0` et ` 2400 ` sont la MÊME largeur."""
        canonical = self.attr_width.canonical_custom_value
        self.assertEqual(canonical("2400.0"), "2400")
        self.assertEqual(canonical(" 2400 "), "2400")
        self.assertEqual(canonical(2400), "2400")
        self.assertEqual(canonical("2400.50"), "2400.5")
        self.assertEqual(canonical("2400.5"), "2400.5")

    def test_02_canonical_form_never_refuses(self):
        """La mise en forme n'est pas une validation — `validate_custom_val` l'est."""
        self.assertEqual(self.attr_width.canonical_custom_value("abc"), "abc")
        self.assertEqual(self.attr_width.canonical_custom_value(""), "")
        self.assertEqual(self.attr_width.canonical_custom_value(False), False)

    def test_03_a_text_attribute_is_left_alone(self):
        """Seul un attribut NUMÉRIQUE a un nombre pour valeur."""
        self.assertEqual(self.attr_note.canonical_custom_value("2400.0"), "2400.0")

    # ── l'affichage ──────────────────────────────────────────────────────────

    def test_04_display_carries_the_unit(self):
        self.assertEqual(self.attr_width.format_custom_value("2400.0"), "2400 mm")
        self.attr_width.uom_id = False
        self.assertEqual(self.attr_width.format_custom_value("2400.0"), "2400")

    def test_05_session_value_is_stored_bare_and_shown_with_the_unit(self):
        custom = self.env["product.config.session.custom.value"].create(
            {
                "attribute_id": self.attr_width.id,
                "cfg_session_id": self.session.id,
                "value": "2400.0",
            }
        )
        self.assertEqual(custom.value, "2400", "la base ne porte que le nombre")
        self.assertEqual(custom.name, "2400 mm", "l'affichage porte l'unité")
        custom.value = " 3000.00 "
        self.assertEqual(custom.value, "3000")
        self.assertEqual(custom.name, "3000 mm")

    def test_06_write_canonicalises_per_attribute(self):
        """Un seul `write` sur deux attributs : chacun a sa mise en forme.

        ⚠️ Sans le regroupement, `self.attribute_id` rend deux enregistrements
        et la mise en forme sauterait EN SILENCE dès le second attribut.
        """
        width = self.env["product.config.session.custom.value"].create(
            {
                "attribute_id": self.attr_width.id,
                "cfg_session_id": self.session.id,
                "value": "1000",
            }
        )
        note = self.env["product.config.session.custom.value"].create(
            {
                "attribute_id": self.attr_note.id,
                "cfg_session_id": self.session.id,
                "value": "hello",
            }
        )
        (width + note).write({"value": "2400.0"})
        self.assertEqual(width.value, "2400", "la largeur est un nombre")
        self.assertEqual(note.value, "2400.0", "la gravure est du texte")

    def test_07_the_variant_custom_value_shows_the_unit_too(self):
        """⚠️ Le cœur d'Odoo affichait « Width: 2400 » — l'unité était perdue
        entre la session et le devis, pour la même valeur."""
        marker = self.env["product.attribute.value"].create(
            {"name": "Custom", "attribute_id": self.attr_width.id, "is_custom": True}
        )
        self.line_width.value_ids = [(4, marker.id)]
        ptav = self.line_width.product_template_value_ids.filtered(
            lambda value: value.product_attribute_value_id == marker
        )
        custom = self.env["product.attribute.custom.value"].create(
            {
                "custom_product_template_attribute_value_id": ptav.id,
                "custom_value": "2400.0",
            }
        )
        self.assertEqual(custom.custom_value, "2400")
        self.assertTrue(
            custom.name.endswith("2400 mm"),
            f"l'unité doit suivre la valeur, lu : {custom.name!r}",
        )

    # ── les bornes parlent la même langue ────────────────────────────────────

    def test_08_bound_messages_carry_the_unit(self):
        self.line_width.write(
            {"has_max_val": True, "max_val": 4000, "step": 50, "has_min_val": True,
             "min_val": 1000}
        )
        message = self.line_width._bounds_error(
            4500, self.line_width._get_bounds()
        )
        self.assertIn("4000 mm", message)
        message = self.line_width._bounds_error(
            1237, self.line_width._get_bounds()
        )
        self.assertIn("50 mm", message)
        self.assertIn("1250 mm", message)

    # ── LA VALEUR DE CATALOGUE, DANS LA LISTE — demande de Gerry, 2026-09-07 ──
    #
    # La règle tenait pour les valeurs SAISIES ; les valeurs rangées (D-081),
    # elles, se lisaient comme des nombres nus dans la liste de l'attribut.

    def test_09_une_valeur_RANGÉE_se_lit_avec_son_unité(self):
        valeur = self.env["product.attribute.value"].create(
            {"name": "2400", "attribute_id": self.attr_width.id}
        )
        self.assertEqual(valeur.name, "2400", "le stocké reste le nombre nu")
        self.assertEqual(valeur.display_value, "2400 mm")

    def test_10_l_affichage_ne_se_STOCKE_pas(self):
        """⚠️ L'unité en base ferait d'un changement d'unité une migration, et
        d'une comparaison de largeurs une comparaison de chaînes (D-160)."""
        champ = self.env["product.attribute.value"]._fields["display_value"]
        self.assertFalse(champ.store, "la valeur affichée ne doit pas être rangée")
        self.assertTrue(champ.readonly, "elle ne doit pas être saisissable")

    def test_11_changer_l_unité_change_l_affichage_sans_toucher_au_nombre(self):
        valeur = self.env["product.attribute.value"].create(
            {"name": "2400", "attribute_id": self.attr_width.id}
        )
        self.attr_width.uom_id = self.env.ref("uom.product_uom_meter")
        valeur.invalidate_recordset(["display_value"])
        self.assertEqual(valeur.name, "2400")
        self.assertEqual(valeur.display_value.split()[0], "2400")
        self.assertNotIn("mm", valeur.display_value)

    def test_12_sans_unité_l_affichage_est_le_NOMBRE_seul(self):
        sans_unite = self.env["product.attribute"].create({
            "name": "Holes", "custom_type": "integer",
            "create_variant": "no_variant",
        })
        valeur = self.env["product.attribute.value"].create(
            {"name": "4", "attribute_id": sans_unite.id}
        )
        self.assertEqual(valeur.display_value, "4")

    def test_13_une_question_qui_n_est_PAS_un_nombre_est_laissée_telle_quelle(self):
        valeur = self.env["product.attribute.value"].create(
            {"name": "Gravure du logo", "attribute_id": self.attr_note.id}
        )
        self.assertEqual(valeur.display_value, "Gravure du logo")

    def test_14_la_colonne_est_DANS_la_liste_et_non_modifiable(self):
        """⓵ Elle doit exister — sinon la demande n'est pas rendue.
        ⓶ Elle doit être en lecture seule : saisir « 2400 mm » créerait une
        valeur distincte de « 2400 », et l'unicité de D-081 serait satisfaite
        par deux doublons pour une seule largeur."""
        from lxml import etree

        arch = self.env["product.attribute"].get_view(
            self.env.ref("product.product_attribute_view_form").id, "form"
        )["arch"]
        colonne = etree.fromstring(arch).xpath(
            "//field[@name='value_ids']/list/field[@name='display_value']"
        )
        self.assertTrue(colonne, "la valeur affichée ne paraît pas dans la liste")
        self.assertEqual(colonne[0].get("readonly"), "1")
        self.assertIn("custom_type", colonne[0].get("column_invisible", ""))
