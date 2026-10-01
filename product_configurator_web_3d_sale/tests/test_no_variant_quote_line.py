"""La ligne de DEVIS porte les réponses « sans variante » de sa configuration — W-99 / D-393.

Depuis l'option A, l'article ne les porte plus : la ligne est le seul endroit où elles vivent
après la commande (description, livraison, fabrication).
"""
from odoo import Command
from odoo.tests import TransactionCase


class NoVariantQuoteLine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.plate = Attribute.create({"name": "Plaque", "create_variant": "dynamic"})
        cls.classic, cls.cine = Value.create([
            {"name": "Classic", "attribute_id": cls.plate.id},
            {"name": "Cine", "attribute_id": cls.plate.id},
        ])
        cls.finish = Attribute.create({"name": "Finition", "create_variant": "no_variant"})
        cls.matte, cls.gloss = Value.create([
            {"name": "Mat", "attribute_id": cls.finish.id},
            {"name": "Brillant", "attribute_id": cls.finish.id},
        ])
        cls.dedication = Attribute.create({"name": "Dedicace", "create_variant": "no_variant",
                                           "val_custom": True, "custom_type": "char"})
        cls.no_dedication = Value.create({"name": "Sans dedicace", "attribute_id": cls.dedication.id})
        cls.tmpl = cls.env["product.template"].create({
            "name": "Drone", "config_ok": True, "list_price": 100.0,
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.plate.id,
                                "value_ids": [Command.set((cls.classic | cls.cine).ids)]}),
                Command.create({"attribute_id": cls.finish.id,
                                "value_ids": [Command.set((cls.matte | cls.gloss).ids)]}),
                Command.create({"attribute_id": cls.dedication.id, "required": False,
                                "value_ids": [Command.set(cls.no_dedication.ids)]}),
            ],
        })
        cls.order = cls.env["sale.order"].create(
            {"partner_id": cls.env["res.partner"].create({"name": "Client W-99"}).id})

    def _confirmed(self, *values):
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
            "value_ids": [Command.set([v.id for v in values])],
        })
        session.action_confirm()
        return session

    def _line(self, session):
        return self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": session.product_id.id,
            "config_session_id": session.id})

    def test_01_la_ligne_recoit_la_reponse_de_sa_configuration(self):
        line = self._line(self._confirmed(self.cine, self.gloss))
        self.assertEqual(line.product_no_variant_attribute_value_ids.product_attribute_value_id,
                         self.gloss)
        self.assertIn("Brillant", line._get_sale_order_line_multiline_description_variants())
        # ⚠️ Et dans la description ENREGISTRÉE : recopiées après la création, les réponses
        # manquaient au texte de la ligne, calculé une fois pour toutes (lot 7).
        self.assertIn("Finition: Brillant", line.name)

    def test_02_reconfiguree_la_ligne_suit(self):
        """D-371 : une configuration rouverte et reconfirmée réécrit l'article de sa ligne."""
        session = self._confirmed(self.cine, self.gloss)
        line = self._line(session)
        session.write({"value_ids": [Command.set((self.cine | self.matte).ids)]})
        line.write({"product_id": session.product_id.id})
        self.assertEqual(line.product_no_variant_attribute_value_ids.product_attribute_value_id,
                         self.matte)
        self.assertIn("Finition: Mat", line.name)
        self.assertNotIn("Brillant", line.name)

    def test_03_un_texte_saisi_s_AJOUTE_a_la_description(self):
        """⚠️ La version d'OCA REMPLAÇAIT la description par les saisies : la finition, qui
        ne vit plus que sur la ligne, aurait disparu du devis."""
        session = self._confirmed(self.cine, self.gloss)
        self.env["product.config.session.custom.value"].create({
            "cfg_session_id": session.id, "attribute_id": self.dedication.id, "value": "Pour Lea"})
        text = self._line(session)._get_sale_order_line_multiline_description_variants()
        self.assertIn("Brillant", text)
        self.assertIn("Pour Lea", text)

    def test_04_reconfigurer_une_ligne_SANS_session_reprend_ses_reponses(self):
        session = self._confirmed(self.cine, self.gloss)
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": session.product_id.id})
        gloss_ptav = self.tmpl.attribute_line_ids.product_template_value_ids.filtered(
            lambda p: p.product_attribute_value_id == self.gloss)
        line.product_no_variant_attribute_value_ids = [Command.set(gloss_ptav.ids)]
        line.reconfigure_product()
        self.assertEqual(line.config_session_id.value_ids, self.cine | self.gloss)
