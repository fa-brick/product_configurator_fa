"""Une pièce VENDUE À PART sur la page — D-368 (lot 3).

Une porte pose, par une question vendue à part, une poignée dont la couleur SUIT celle de
la porte. Ce qui est éprouvé : la ligne à part (article, quantité, prix), la variante de la
poignée qui naît à la confirmation MÊME si le client ne l'a pas touchée — avec la couleur
suivie —, et ce que l'éditeur apprend pour alerter sur une pièce intégrée.
"""
import shutil
import sys
from unittest import skipUnless

from odoo import Command
from odoo.api import call_kw
from odoo.tests import TransactionCase, tagged

HAS_NODE = bool(shutil.which("node") or shutil.which("nodejs"))


@tagged("post_install", "-at_install")
class TestSaleSeparatelyPage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.color = Attribute.create({"name": "Couleur"})
        cls.white, cls.black = Value.create([
            {"name": "Blanc", "attribute_id": cls.color.id},
            {"name": "Noir", "attribute_id": cls.color.id},
        ])
        cls.handle_tmpl = cls.env["product.template"].create({
            "name": "Poignée", "list_price": 10.0,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.color.id,
                "value_ids": [Command.set((cls.white | cls.black).ids)],
            })],
        })
        cls.option = Attribute.create({"name": "Option poignée", "create_variant": "no_variant",
                                       "value_type": "product"})
        cls.none, cls.handle_value = Value.create([
            {"name": "Sans poignée", "attribute_id": cls.option.id},
            {"name": "Poignée", "attribute_id": cls.option.id,
             "product_id": cls.handle_tmpl.product_variant_ids[:1].id},
        ])
        cls.door_tmpl = cls.env["product.template"].create({
            "name": "Porte", "config_ok": True,
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.color.id,
                                "value_ids": [Command.set((cls.white | cls.black).ids)]}),
                Command.create({"attribute_id": cls.option.id, "required": False,
                                "sale_separately": True,
                                "value_ids": [Command.set((cls.none | cls.handle_value).ids)]}),
            ],
        })
        Model3d = cls.env["product.model3d"]
        cls.handle = Model3d.create({"name": "Poignée", "product_tmpl_id": cls.handle_tmpl.id})
        cls.door = Model3d.create({"name": "Porte", "product_tmpl_id": cls.door_tmpl.id,
                                   "piece_type": "assembly"})
        cls.link = cls.env["product.model3d.component"].create({
            "parent_id": cls.door.id, "child_id": cls.handle.id,
            "swap_attribute_id": cls.option.id,
        })
        # ⚠️ **UNE LISTE DE PRIX À SOI, VIDE.** Le prix d'une ligne à part passe par la liste
        # de l'utilisateur (`web_separate_lines`), donc par celle de la BASE où tourne le
        # test : sur fabk18, la liste « Par défaut » portait une règle globale « prix fixe
        # 0 » (4 août → 30 septembre 2026), et trois tests tombaient à 0 au lieu de 10 et
        # 12 sans que le code soit en cause (2026-09-30). Le test fixe la sienne.
        cls.pricelist = cls.env["product.pricelist"].create({"name": "Sans règle"})
        cls.env.user.partner_id.specific_property_product_pricelist = cls.pricelist

    def _session(self, *values):
        # ⓘ Créée VIDE puis répondue : à la création, la session pose d'office le défaut
        # de chaque question, et « Noir » s'ajouterait au « Blanc » par défaut.
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.door_tmpl.id, "user_id": self.env.user.id,
        })
        session.write({"value_ids": [Command.set([v.id for v in values])]})
        return session

    def test_l_editeur_sait_que_la_piece_est_vendue_a_part(self):
        self.assertIs(self.link.customer_answers_ordered(), True)
        self.door_tmpl.attribute_line_ids.filtered(
            lambda l: l.attribute_id == self.option).sale_separately = False
        self.assertIs(self.link.customer_answers_ordered(), False)

    def test_par_le_chemin_RPC_de_l_editeur(self):
        """⚠️ Appelées comme le CLIENT les appelle (`orm.call`) : l'une sur un lien, l'autre
        sans. Une méthode insérée juste avant `can_edit_conditions` lui avait VOLÉ son
        `@api.model` — un appel direct sur l'enregistrement passait quand même (L-430)."""
        Link = self.env["product.model3d.component"]
        self.assertIs(call_kw(Link, "can_edit_conditions", [], {}), True)
        self.assertIs(call_kw(Link, "customer_answers_ordered", [[self.link.id]], {}), True)

    def test_sans_piece_aucune_ligne_a_part(self):
        self.assertEqual(self._session(self.black, self.none).web_separate_lines(), [])

    def test_la_ligne_a_part_porte_la_piece_dans_la_couleur_SUIVIE(self):
        lines = self._session(self.black, self.handle_value).web_separate_lines()
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual((line["attributeId"], line["valueId"], line["qty"], line["linkId"]),
                         (self.option.id, self.handle_value.id, 1, self.link.id))
        product = self.env["product.product"].browse(line["productId"])
        self.assertEqual(product.product_template_attribute_value_ids.product_attribute_value_id,
                         self.black)
        self.assertEqual(line["price"], 10.0)

    def test_la_ligne_a_part_suit_la_LISTE_DE_PRIX(self):
        """C'est pour elle que le prix passe par la liste de l'utilisateur : le panier la
        facture, la page doit annoncer le même prix."""
        self.env["product.pricelist.item"].create({
            "pricelist_id": self.pricelist.id, "applied_on": "1_product",
            "product_tmpl_id": self.handle_tmpl.id,
            "compute_price": "fixed", "fixed_price": 7.0,
        })
        lines = self._session(self.black, self.handle_value).web_separate_lines()
        self.assertEqual([line["price"] for line in lines], [7.0])

    def test_la_variante_de_la_piece_nait_meme_non_touchee(self):
        """⚠️ Avant D-368, une pièce que le client n'avait pas répondue ne recevait aucune
        variante ; vendue à part, il lui faut un article."""
        session = self._session(self.black, self.handle_value)
        born = session._web_confirm_children()
        variant = self.env["product.product"].browse(born[str(self.link.id)])
        self.assertEqual(variant.product_tmpl_id, self.handle_tmpl)
        self.assertEqual(variant.product_template_attribute_value_ids.product_attribute_value_id,
                         self.black)
        self.assertEqual(session.web_separate_lines()[0]["productId"], variant.id)

    def test_la_page_recoit_les_lignes_et_le_TOTAL(self):
        """Le total affiché = le produit + ses lignes à part ; le détail va au panier."""
        session = self._session(self.black, self.handle_value)
        state = session.web_state()
        self.assertEqual(len(state["separateLines"]), 1)
        self.assertEqual(state["total"], state["price"] + 10.0)
        self.assertEqual(self._session(self.black, self.none).web_state()["separateLines"], [])

    # ── La QUANTITÉ compte les POSES — répétitions et miroirs (D-375) ─────────────
    # ⚠️ Le moteur compte, dans Node : ces tests sont sautés sans lui, sauf celui du repli.

    def setUp(self):
        super().setUp()
        count_module = sys.modules[type(self.env["product.model3d"])._count_poses.__module__]
        count_module._MEMORY.clear()
        self.Function = self.env["product.model3d.function.assembly"]

    def _mirror(self):
        return self.Function.create({
            "model3d_id": self.door.id, "op": "mirror", "link_ids": [Command.set(self.link.ids)],
            "params": {"mirrorX": {"value": True}, "axisX": {"value": 400}},
        })

    @skipUnless(HAS_NODE, "Node.js is not installed")
    def test_une_repetition_multiplie_la_quantite(self):
        self.Function.create({
            "model3d_id": self.door.id, "op": "repeat", "link_ids": [Command.set(self.link.ids)],
            "params": {"xCount": {"expr": "1 + 2", "default": 1}, "pitchX": {"value": 100}},
        })
        lines = self._session(self.black, self.handle_value).web_separate_lines()
        self.assertEqual([line["qty"] for line in lines], [3])

    @skipUnless(HAS_NODE, "Node.js is not installed")
    def test_le_miroir_d_une_piece_REVERSIBLE_reste_sur_sa_ligne(self):
        self.handle.reversible = "reversible"
        self._mirror()
        lines = self._session(self.black, self.handle_value).web_separate_lines()
        self.assertEqual([line["qty"] for line in lines], [2])

    @skipUnless(HAS_NODE, "Node.js is not installed")
    def test_le_miroir_d_une_piece_CHIRALE_passe_sous_son_jumeau(self):
        """La poignée gauche a pour image la droite : deux lignes, la même couleur."""
        right_tmpl = self.env["product.template"].create({
            "name": "Poignée droite", "list_price": 12.0,
            "attribute_line_ids": [Command.create({
                "attribute_id": self.color.id,
                "value_ids": [Command.set((self.white | self.black).ids)],
            })],
        })
        self.handle.reversible = "chiral"
        self.env["product.model3d"].create({
            "name": "Poignée droite", "product_tmpl_id": right_tmpl.id,
            "mirror_source_id": self.handle.id,
        })
        self._mirror()
        session = self._session(self.black, self.handle_value)
        lines = session.web_separate_lines()
        self.assertEqual([(line["qty"], bool(line.get("mirrored"))) for line in lines],
                         [(1, False), (1, True)])
        self.assertEqual(lines[1]["price"], 12.0)
        # ⓘ Avant la confirmation, le jumeau n'a pas encore d'article ; après, sa variante
        # naît dans la couleur de l'original.
        session._web_confirm_children()
        twin = self.env["product.product"].browse(session.web_separate_lines()[1]["productId"])
        self.assertEqual(twin.product_tmpl_id, right_tmpl)
        self.assertEqual(twin.product_template_attribute_value_ids.product_attribute_value_id,
                         self.black)

    def test_sans_node_la_quantite_d_avant_et_le_journal_le_dit(self):
        self._mirror()
        self.env["ir.config_parameter"].sudo().set_param(
            "product_editor.node_path", "/nonexistent/node")
        with self.assertLogs(level="WARNING") as logs:
            lines = self._session(self.black, self.handle_value).web_separate_lines()
        self.assertEqual([line["qty"] for line in lines], [1])
        self.assertTrue(any("one per placement" in message for message in logs.output))
