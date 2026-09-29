"""Une ligne de DEVIS se corrige ; une COMMANDE, non — D-371. Et ses pièces à part suivent (D-368).

Gerry : « quand on est à l'état de devis, rien n'est joué ; c'est uniquement lors du passage
en commande que le variant est concret ». Et : supprimer la ligne d'une pièce vendue à part
la désélectionne à la réouverture du configurateur.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReopenQuote(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.handle = cls.env["product.product"].create(
            {"name": "Poignée", "list_price": 10.0, "sale_ok": True})
        cls.color = Attribute.create({"name": "Couleur"})
        cls.white, cls.black = Value.create([
            {"name": "Blanc", "attribute_id": cls.color.id},
            {"name": "Noir", "attribute_id": cls.color.id},
        ])
        cls.option = Attribute.create({"name": "Option poignée", "create_variant": "no_variant",
                                       "value_type": "product"})
        cls.none, cls.with_handle = Value.create([
            {"name": "Sans poignée", "attribute_id": cls.option.id},
            {"name": "Poignée", "attribute_id": cls.option.id, "product_id": cls.handle.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte", "config_ok": True, "list_price": 100.0,
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.color.id,
                                "value_ids": [Command.set((cls.white | cls.black).ids)]}),
                Command.create({"attribute_id": cls.option.id, "required": False,
                                "sale_separately": True,
                                "value_ids": [Command.set((cls.none | cls.with_handle).ids)]}),
            ],
        })
        option_line = cls.tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id == cls.option)
        option_line.default_val = cls.none
        cls.partner = cls.env["res.partner"].create({"name": "Client d'essai"})

    def _confirmed_line(self, *values, client_lines=False):
        """Une ligne de devis dont la configuration vient d'être CONFIRMÉE."""
        session = self.env["product.config.session"].create_get_session(
            self.tmpl.id, force_create=True)
        session.value_ids = [Command.set([v.id for v in values])]
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": order.id, "product_id": session.create_get_variant().id,
            "product_uom_qty": 1, "config_session_id": session.id,
        })
        session.with_context(cfg_client_lines=client_lines).web_confirm()
        return line, session

    # ── les pièces à part, depuis le LIEN ──────────────────────────────────
    def test_confirmee_par_le_lien_la_piece_a_sa_ligne_rattachee(self):
        line, _ = self._confirmed_line(self.black, self.with_handle)
        self.assertEqual(line.linked_line_ids.product_id, self.handle)

    def test_confirmee_par_le_dialogue_le_serveur_ne_la_double_pas(self):
        line, _ = self._confirmed_line(self.black, self.with_handle, client_lines=True)
        self.assertFalse(line.linked_line_ids)

    # ── rouvrir : un devis oui, une commande non ───────────────────────────
    def test_un_devis_se_rouvre(self):
        _, session = self._confirmed_line(self.black, self.none)
        self.assertEqual(session.state, "done")
        self.assertTrue(session._web_reopen_if_open_quote())
        self.assertEqual(session.state, "draft")

    def test_une_commande_reste_close(self):
        line, session = self._confirmed_line(self.black, self.none)
        line.order_id.action_confirm()
        self.assertFalse(session._web_reopen_if_open_quote())
        self.assertEqual(session.state, "done")

    def test_sans_ligne_de_devis_rien_ne_se_rouvre(self):
        """Une configuration de la boutique n'a pas de devis qui la porte."""
        session = self.env["product.config.session"].create_get_session(
            self.tmpl.id, force_create=True)
        session.value_ids = [Command.set(self.black.ids)]
        session.web_confirm()
        self.assertFalse(session._web_reopen_if_open_quote())

    def test_le_dialogue_du_devis_rouvre_la_ligne(self):
        _, session = self._confirmed_line(self.black, self.none)
        opened = self.tmpl.web3d_open_configuration(session_id=session.id)
        self.assertEqual(opened["sessionId"], session.id)
        self.assertEqual(opened["state"]["state"], "draft")

    # ── la ligne supprimée désélectionne la pièce ──────────────────────────
    def test_la_piece_dont_la_ligne_est_supprimee_est_deselectionnee(self):
        line, session = self._confirmed_line(self.black, self.with_handle)
        line.linked_line_ids.unlink()
        session._web_reopen_if_open_quote()
        self.assertNotIn(self.with_handle, session.value_ids)
        self.assertIn(self.none, session.value_ids)          # le défaut sans pièce
        self.assertIn(self.black, session.value_ids)          # le reste ne bouge pas

    def test_la_piece_encore_au_devis_reste_choisie(self):
        _, session = self._confirmed_line(self.black, self.with_handle)
        session._web_reopen_if_open_quote()
        self.assertIn(self.with_handle, session.value_ids)

    def test_reconfigurer_sans_piece_retire_sa_ligne(self):
        line, session = self._confirmed_line(self.black, self.with_handle)
        session._web_reopen_if_open_quote()
        session.value_ids = [Command.set((self.black | self.none).ids)]
        session.web_confirm()
        self.assertFalse(line.linked_line_ids)

    def test_confirmer_REND_la_main(self):
        """⚠️ Sans cela, le dialogue rouvert se heurtait au dialogue qu'on venait de fermer
        (« X est en train de configurer »), le même commercial contre lui-même."""
        session = self.env["product.config.session"].create_get_session(
            self.tmpl.id, force_create=True)
        session.value_ids = [Command.set(self.black.ids)]
        session._take_hand("page-fermee")
        session.web_confirm()
        self.assertTrue(session._hand_is_free())
