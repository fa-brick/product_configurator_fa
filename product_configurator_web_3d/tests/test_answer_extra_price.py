"""Le SUPPLÉMENT de chaque réponse sur la page — W-100, lot 1 (D-396).

Ce qui est éprouvé : le libellé `extra` de chaque valeur servie par `web_state` — forfait,
négatif, nul, valeur qui désigne un produit, taux au m² avant puis après les cotes, aucune
pastille sur une cote de grille — toujours au prix CATALOGUE, jamais par la liste de prix.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import format_amount

from odoo.addons.product_configurator_web_3d.models.product_config_price_label import MINUS


@tagged("post_install", "-at_install")
class TestAnswerExtraPrice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        uom_mm = cls.env.ref("uom.product_uom_millimeter")
        cls.finish = Attribute.create({"name": "Finition W-100", "create_variant": "dynamic"})
        cls.matt, cls.gloss, cls.rough = Value.create([
            {"name": "Mat W-100", "attribute_id": cls.finish.id},
            {"name": "Brillant W-100", "attribute_id": cls.finish.id},
            {"name": "Brut W-100", "attribute_id": cls.finish.id},
        ])
        cls.part_tmpl = cls.env["product.template"].create({
            "name": "Plaque W-100", "list_price": 20.0,
        })
        cls.option = Attribute.create({"name": "Plaque W-100", "create_variant": "dynamic",
                                       "value_type": "product"})
        cls.none, cls.plate = Value.create([
            {"name": "Sans plaque W-100", "attribute_id": cls.option.id},
            {"name": "Plaque W-100", "attribute_id": cls.option.id,
             "product_id": cls.part_tmpl.product_variant_ids[:1].id},
        ])
        cls.width, cls.height = Attribute.create([
            {"name": "Largeur W-100", "val_custom": True, "custom_type": "float",
             "uom_id": uom_mm.id, "create_variant": "dynamic"},
            {"name": "Hauteur W-100", "val_custom": True, "custom_type": "float",
             "uom_id": uom_mm.id, "create_variant": "dynamic"},
        ])
        cls.width_2000 = Value.create({"name": "2000", "attribute_id": cls.width.id})
        cls.lacquer = Attribute.create({"name": "Laquage W-100", "price_mode": "per_sqm",
                                        "create_variant": "dynamic"})
        cls.white, cls.ral = Value.create([
            {"name": "Blanc W-100", "attribute_id": cls.lacquer.id},
            {"name": "RAL W-100", "attribute_id": cls.lacquer.id,
             "default_extra_price_sqm": 25},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte W-100", "config_ok": True, "list_price": 100.0,
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.finish.id, "required": False,
                                "value_ids": [Command.set((cls.matt | cls.gloss | cls.rough).ids)]}),
                Command.create({"attribute_id": cls.option.id, "required": False,
                                "value_ids": [Command.set((cls.none | cls.plate).ids)]}),
                Command.create({"attribute_id": cls.width.id, "required": False, "custom": True,
                                "dimension_role": "axis_x",
                                "value_ids": [Command.set(cls.width_2000.ids)]}),
                Command.create({"attribute_id": cls.height.id, "required": False, "custom": True,
                                "dimension_role": "axis_y"}),
                Command.create({"attribute_id": cls.lacquer.id, "required": False,
                                "price_mode": "per_sqm",
                                "value_ids": [Command.set((cls.white | cls.ral).ids)]}),
            ],
        })
        ptavs = cls.tmpl.attribute_line_ids.product_template_value_ids
        by_value = {ptav.product_attribute_value_id: ptav for ptav in ptavs}
        by_value[cls.gloss].price_extra = 5.0
        by_value[cls.rough].price_extra = -3.0
        # ⓘ Un supplément posé sur une COTE : il ne doit pas s'afficher (cas 4).
        by_value[cls.width_2000].price_extra = 7.0
        # ⚠️ UNE LISTE DE PRIX À SOI : celle de la base porte parfois des règles ([[L-453]]).
        cls.pricelist = cls.env["product.pricelist"].create({"name": "Sans règle W-100"})
        cls.env.user.partner_id.specific_property_product_pricelist = cls.pricelist
        cls.currency = cls.pricelist.currency_id

    def _session(self, typed=None):
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
        })
        session.write({"value_ids": [Command.clear()]})
        for attribute, text in (typed or {}).items():
            self.env["product.config.session.custom.value"].create({
                "attribute_id": attribute.id, "cfg_session_id": session.id, "value": text,
            })
        return session

    def _extras(self, session, attribute):
        question = next(q for q in session.web_state()["attributes"] if q["id"] == attribute.id)
        return {value["id"]: value["extra"] for value in question["values"]}

    def _label(self, amount, sign="+", suffix=""):
        return sign + format_amount(self.env, amount, self.currency) + suffix

    def test_un_forfait_s_affiche_signe_et_un_supplement_nul_ne_s_affiche_pas(self):
        extras = self._extras(self._session(), self.finish)
        self.assertEqual(extras[self.gloss.id], self._label(5.0))
        self.assertEqual(extras[self.rough.id], self._label(3.0, sign=MINUS))
        self.assertIsNone(extras[self.matt.id])

    def test_une_valeur_produit_affiche_le_prix_du_produit(self):
        extras = self._extras(self._session(), self.option)
        self.assertEqual(extras[self.plate.id], self._label(20.0))
        self.assertIsNone(extras[self.none.id])

    def test_le_supplement_reste_au_prix_CATALOGUE_malgre_la_liste_de_prix(self):
        """⚠️ Une règle de la liste peut dépendre de la combinaison entière : la pastille
        montre le catalogue, le total seul passe par la liste (D-396)."""
        self.env["product.pricelist.item"].create({
            "pricelist_id": self.pricelist.id, "applied_on": "3_global",
            "compute_price": "percentage", "percent_price": 50,
        })
        session = self._session()
        self.assertEqual(self._extras(session, self.option)[self.plate.id], self._label(20.0))
        self.assertEqual(self._extras(session, self.finish)[self.gloss.id], self._label(5.0))

    def test_un_taux_au_m2_s_affiche_en_TAUX_tant_qu_une_cote_manque(self):
        extras = self._extras(self._session({self.width: "2300"}), self.lacquer)
        self.assertEqual(extras[self.ral.id], self._label(25.0, suffix="/m²"))
        self.assertIsNone(extras[self.white.id])

    def test_un_taux_au_m2_s_affiche_en_MONTANT_une_fois_les_cotes_connues(self):
        """2,3 m × 2,1 m = 4,83 m² à 25 €/m² → 120,75."""
        extras = self._extras(self._session({self.width: "2300", self.height: "2100"}),
                              self.lacquer)
        self.assertEqual(extras[self.ral.id], self._label(120.75))

    def test_aucune_pastille_sur_une_cote_de_grille(self):
        extras = self._extras(self._session(), self.width)
        self.assertEqual(extras, {self.width_2000.id: None})
