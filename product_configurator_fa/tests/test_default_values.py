"""Des valeurs PAR DÉFAUT incompatibles n'empêchent pas d'ouvrir une configuration.

Constat de Gerry (2026-09-29, JeNo) : « Configurer » tombait en erreur — le défaut de
« Bumper Avant » (Ciné) n'est offert qu'avec une Cam plate Ciné, et la Cam plate par défaut est
Classic. Et le relais de l'erreur levait lui-même une `AttributeError` (`exc.name`).
"""
from odoo import Command
from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon


class DefaultValues(BaseCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.plate = Attribute.create({"name": "Cam plate"})
        cls.classic, cls.cine = Value.create([
            {"name": "Classic", "attribute_id": cls.plate.id},
            {"name": "Ciné", "attribute_id": cls.plate.id},
        ])
        cls.bumper = Attribute.create({"name": "Bumper Avant"})
        cls.bumper_cine, cls.bumper_classic = Value.create([
            {"name": "Ciné", "attribute_id": cls.bumper.id},
            {"name": "Classic", "attribute_id": cls.bumper.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Drone", "config_ok": True,
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.plate.id, "default_val": cls.classic.id,
                                "value_ids": [Command.set((cls.classic | cls.cine).ids)]}),
                Command.create({"attribute_id": cls.bumper.id, "required": False,
                                "default_val": cls.bumper_cine.id,
                                "value_ids": [Command.set(
                                    (cls.bumper_cine | cls.bumper_classic).ids)]}),
            ],
        })
        bumper_line = cls.tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id == cls.bumper)
        domain = cls.env["product.config.domain"].create({
            "name": "Cam plate Ciné",
            "domain_line_ids": [Command.create({
                "attribute_id": cls.plate.id, "condition": "in", "operator": "and",
                "value_ids": [Command.set(cls.cine.ids)],
            })],
        })
        cls.env["product.config.line"].create({
            "product_tmpl_id": cls.tmpl.id, "attribute_line_id": bumper_line.id,
            "value_ids": [Command.set(cls.bumper_cine.ids)], "domain_id": domain.id,
        })

    def test_un_defaut_indisponible_n_empeche_pas_d_ouvrir_la_configuration(self):
        session = self.env["product.config.session"].create_get_session(
            self.tmpl.id, force_create=True)
        self.assertTrue(session)

    def test_le_defaut_indisponible_est_ecarte_les_autres_restent(self):
        Session = self.env["product.config.session"]
        kept = Session._available_default_val_ids(
            self.tmpl, [self.classic.id, self.bumper_cine.id])
        self.assertEqual(kept, [self.classic.id])

    def test_un_vrai_refus_se_lit_et_ne_leve_plus_AttributeError(self):
        """Deux valeurs pour une question à réponse unique : refus LISIBLE."""
        with self.assertRaises(ValidationError) as caught:
            self.env["product.config.session"].create({
                "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
                "value_ids": [Command.set((self.classic | self.cine).ids)],
            })
        self.assertIn("Cam plate", str(caught.exception))
