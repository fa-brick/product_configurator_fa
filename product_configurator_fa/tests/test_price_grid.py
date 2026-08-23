from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon


class PriceGrid(BaseCommon):
    """La grille tarifaire — lot 3 (D-083, D-084, D-093, D-161, D-162).

    Le barème est celui travaillé dans D-083, et il est délibérément NON
    ADDITIF : l'écart entre les deux lignes vaut 40, 50 puis 60 selon la
    colonne. C'est ce qui interdit de le représenter par des `price_extra`.
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
                "create_variant": "dynamic",
            }
        )
        cls.attr_height = cls.env["product.attribute"].create(
            {
                "name": "Height",
                "val_custom": True,
                "custom_type": "float",
                "uom_id": cls.uom_mm.id,
                "create_variant": "dynamic",
            }
        )
        cls.attr_lacquer = cls.env["product.attribute"].create(
            {
                "name": "Lacquering",
                "price_mode": "per_sqm",
                "create_variant": "dynamic",
            }
        )
        cls.value_standard = cls.env["product.attribute.value"].create(
            {"name": "Standard white", "attribute_id": cls.attr_lacquer.id}
        )
        cls.value_premium = cls.env["product.attribute.value"].create(
            {
                "name": "RAL 8003",
                "attribute_id": cls.attr_lacquer.id,
                "default_extra_price_sqm": 25,
            }
        )
        cls.template = cls.env["product.template"].create(
            {"name": "Sliding Door", "config_ok": True, "list_price": 200}
        )
        cls.line_width = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attr_width.id,
                "custom": True,
                "required": False,
                "dimension_role": "axis_x",
            }
        )
        cls.line_height = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attr_height.id,
                "custom": True,
                "required": False,
                "dimension_role": "axis_y",
            }
        )
        cls.line_lacquer = cls.env["product.template.attribute.line"].create(
            {
                "product_tmpl_id": cls.template.id,
                "attribute_id": cls.attr_lacquer.id,
                "required": False,
                "price_mode": "per_sqm",
                "value_ids": [
                    (6, 0, [cls.value_standard.id, cls.value_premium.id])
                ],
            }
        )
        cls.grid = cls._make_grid(cls, "2026 tariff")

    def _make_grid(self, name, date_start=False, date_end=False):
        grid = self.env["product.price.grid"].create(
            {
                "name": name,
                "product_tmpl_id": self.template.id,
                "date_start": date_start,
                "date_end": date_end,
            }
        )
        brackets = {}
        for axis, bounds in (("x", (2000, 2500, 3000)), ("y", (2100, 2400))):
            for bound in bounds:
                brackets[(axis, bound)] = self.env[
                    "product.price.grid.bracket"
                ].create({"grid_id": grid.id, "axis": axis, "max_value": bound})
        prices = {
            (2000, 2100): 420, (2500, 2100): 480, (3000, 2100): 540,
            (2000, 2400): 460, (2500, 2400): 530, (3000, 2400): 600,
        }
        for (x, y), price in prices.items():
            self.env["product.price.grid.cell"].create(
                {
                    "grid_id": grid.id,
                    "x_bracket_id": brackets[("x", x)].id,
                    "y_bracket_id": brackets[("y", y)].id,
                    "price": price,
                }
            )
        return grid

    def _variant(self, width, height, lacquer=None):
        """Une variante configurée, par le chemin réel du configurateur."""
        session = self.env["product.config.session"].create(
            {"product_tmpl_id": self.template.id, "user_id": self.env.user.id}
        )
        for attribute, value in (
            (self.attr_width, width),
            (self.attr_height, height),
        ):
            self.env["product.config.session.custom.value"].create(
                {
                    "attribute_id": attribute.id,
                    "cfg_session_id": session.id,
                    "value": value,
                }
            )
        value_ids = [lacquer.id] if lacquer else []
        return session.create_get_variant(value_ids=value_ids)

    # ── la lecture de la grille ──────────────────────────────────────────────

    def test_01_a_value_takes_its_bracket(self):
        """2 300 prend la colonne « jusqu'à 2 500 » — par palier, jamais
        interpolé."""
        self.assertEqual(self.grid.get_price(2300, 2000), 480)
        self.assertEqual(self.grid.get_price(2000, 2100), 420)
        self.assertEqual(self.grid.get_price(2500.0, 2400), 530)

    def test_02_out_of_grid_is_none_never_zero(self):
        """Hors grille est un cas à SIGNALER, pas un prix de zéro."""
        self.assertIsNone(self.grid.get_price(3200, 2100))
        self.assertIsNone(self.grid.get_price(2000, 2600))

    def test_03_the_grid_is_not_additive(self):
        """Le contrôle de D-083 : soustraire deux lignes, l'écart varie."""
        gaps = [
            self.grid.get_price(x, 2400) - self.grid.get_price(x, 2100)
            for x in (2000, 2500, 3000)
        ]
        self.assertEqual(gaps, [40, 50, 60])
        self.assertNotEqual(
            len(set(gaps)), 1, "si l'écart était constant, price_extra suffirait"
        )

    # ── les gardes ───────────────────────────────────────────────────────────

    def test_04_overlapping_grids_are_refused(self):
        with self.assertRaises(ValidationError):
            self._make_grid("2027 tariff")

    def test_05_dates_select_the_grid(self):
        self.grid.date_end = "2026-12-31"
        later = self._make_grid(
            "2027 tariff", date_start="2027-01-01", date_end="2027-12-31"
        )
        self.assertEqual(self.template._get_price_grid(date="2026-06-01"), self.grid)
        self.assertEqual(self.template._get_price_grid(date="2027-06-01"), later)
        self.assertFalse(
            self.template._get_price_grid(date="2028-01-01"),
            "passé la dernière grille, il n'y a plus de prix — et c'est un cas "
            "à signaler, pas à combler avec le tarif d'hier (D-083)",
        )

    def test_06_a_missing_grid_is_flagged_on_arrival(self):
        """On ne laisse pas configurer dix minutes pour annoncer ensuite qu'on
        ne sait pas vendre (D-083)."""
        bare = self.env["product.template"].create(
            {"name": "Unpriced Door", "config_ok": True}
        )
        self.assertTrue(bare.price_grid_warning)
        self.assertFalse(self.template.price_grid_warning)

    def test_07_one_role_one_holder(self):
        with self.assertRaises(ValidationError):
            self.env["product.template.attribute.line"].create(
                {
                    "product_tmpl_id": self.template.id,
                    "attribute_id": self.env["product.attribute"]
                    .create(
                        {
                            "name": "Depth",
                            "val_custom": True,
                            "custom_type": "float",
                            "uom_id": self.uom_mm.id,
                        }
                    )
                    .id,
                    "custom": True,
                    "required": False,
                    "dimension_role": "axis_x",
                }
            )

    # ── le prix de vente ─────────────────────────────────────────────────────

    def test_08_list_price_becomes_a_from_price(self):
        """« À partir de » = le minimum de la grille — sinon la fiche annonce un
        prix auquel aucune vente ne se fait (D-093)."""
        self.assertEqual(self.template.list_price, 420)

    def test_09_the_variant_price_comes_from_the_grid(self):
        variant = self._variant(2300, 2100)
        prices = variant._price_compute("list_price")
        self.assertEqual(prices[variant.id], 480)

    def test_10_a_partner_discount_applies_to_the_grid_price(self):
        """LE critère du lot 3 : « professionnel −10 % » sur le prix de GRILLE,
        sans le moindre réglage."""
        variant = self._variant(2300, 2100)
        pricelist = self.env["product.pricelist"].create(
            {
                "name": "Professional -10%",
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "percentage",
                            "percent_price": 10,
                        },
                    )
                ],
            }
        )
        self.assertAlmostEqual(
            pricelist._get_product_price(variant, 1.0), 432.0, places=2
        )

    # ── le prix au m² ────────────────────────────────────────────────────────

    def test_11_a_per_sqm_extra_multiplies_the_surface(self):
        """25 €/m² × (2,3 m × 2,1 m) = 120,75 — la surface vient des DEUX AXES."""
        variant = self._variant(2300, 2100, lacquer=self.value_premium)
        prices = variant._price_compute("list_price")
        self.assertAlmostEqual(prices[variant.id], 480 + 120.75, places=2)

    def test_12_the_rate_never_lands_in_price_extra(self):
        """⚠️ Odoo somme `price_extra` partout : 25 €/m² y serait facturé 25 €."""
        ptav = self.line_lacquer.product_template_value_ids.filtered(
            lambda value: value.product_attribute_value_id == self.value_premium
        )
        self.assertEqual(ptav.price_extra, 0)
        self.assertEqual(ptav.price_extra_sqm, 25, "le taux du catalogue est recopié")

    def test_13_a_surface_needs_a_unit(self):
        """Supposer le millimètre, c'est se tromper d'un facteur un million."""
        self.attr_width.uom_id = False
        with self.assertRaises(ValidationError):
            self.template._grid_surface(2300, 2100)

    def test_14_the_session_prices_before_anything_is_resolved(self):
        """Pendant la configuration, la cote est encore une saisie libre."""
        session = self.env["product.config.session"].create(
            {"product_tmpl_id": self.template.id, "user_id": self.env.user.id}
        )
        price = session.get_cfg_price(
            value_ids=[self.value_premium.id],
            custom_vals={self.attr_width.id: 2300, self.attr_height.id: 2100},
        )
        self.assertAlmostEqual(price, 480 + 120.75, places=2)

    # ── le champ informatif ──────────────────────────────────────────────────

    def test_15_the_stored_grid_price_is_refreshed_nightly(self):
        variant = self._variant(2300, 2100)
        self.assertEqual(variant.grid_price, 0, "rien n'est stocké à la création")
        self.env["product.product"]._cron_refresh_grid_price()
        self.assertEqual(variant.grid_price, 480)

    def test_16_the_ui_sales_price_still_shows_the_from_price(self):
        """⚠️ LIMITE CONNUE, épinglée ici pour que personne ne la découvre.

        D-093 accroche la grille à `_price_compute`, par où passent les listes
        de prix, les devis, les rapports et le portail. Mais `lst_price` du
        cœur est un compute SÉPARÉ (`list_price + price_extra`) : la « Sales
        Price » affichée sur la fiche variante montre donc le « à partir de »,
        pas le prix de grille. C'est le champ `grid_price` (D-084) qui dit le
        vrai, et ce test tombera le jour où l'un des deux changera.
        """
        variant = self._variant(2300, 2100)
        self.assertEqual(variant.lst_price, 420)
        self.assertEqual(variant._price_compute("list_price")[variant.id], 480)
