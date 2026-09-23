# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""RÉPONDRE aux questions d'une pièce POSÉE — D-332, D-333.

Une porte pose une poignée dont la COULEUR est libre, et un rail dont l'auteur a fixé
toutes les questions par le lien. Ce qui est éprouvé : seule la poignée est un
placement réglable ; y répondre écrit la session, entre dans la définition, et fait
naître la variante de la poignée à la confirmation. Ce qui doit être REFUSÉ : répondre
à ce que l'auteur a fixé.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlacements(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.couleur = Attribute.create({"name": "Couleur de poignée"})
        cls.blanc, cls.noir = Value.create([
            {"name": "Blanc", "attribute_id": cls.couleur.id},
            {"name": "Noir", "attribute_id": cls.couleur.id},
        ])
        cls.longueur = Attribute.create({"name": "Longueur de rail"})
        cls.courte, cls.longue = Value.create([
            {"name": "Courte", "attribute_id": cls.longueur.id},
            {"name": "Longue", "attribute_id": cls.longueur.id},
        ])
        cls.poignee_tmpl = cls.env["product.template"].create({
            "name": "Poignée",
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.couleur.id,
                "value_ids": [Command.set((cls.blanc | cls.noir).ids)],
            })],
        })
        cls.rail_tmpl = cls.env["product.template"].create({
            "name": "Rail",
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.longueur.id,
                "value_ids": [Command.set((cls.courte | cls.longue).ids)],
            })],
        })
        Model3d = cls.env["product.model3d"]
        cls.poignee = Model3d.create({"name": "Poignée", "product_tmpl_id": cls.poignee_tmpl.id})
        cls.rail = Model3d.create({"name": "Rail", "product_tmpl_id": cls.rail_tmpl.id})
        cls.porte_tmpl = cls.env["product.template"].create({
            "name": "Porte de garage", "config_ok": True,
        })
        cls.porte = Model3d.create({
            "name": "Porte", "product_tmpl_id": cls.porte_tmpl.id, "piece_type": "assembly",
        })
        Link = cls.env["product.model3d.component"]
        cls.link_poignee = Link.create({"parent_id": cls.porte.id, "child_id": cls.poignee.id})
        cls.link_rail = Link.create({
            "parent_id": cls.porte.id, "child_id": cls.rail.id,
            "attribute_overrides": {str(cls.longueur.id): {"value": "Longue"}},
        })
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": cls.porte_tmpl.id, "user_id": cls.env.user.id,
        })

    def _placements(self):
        return self.session.web_state()["placements"]

    # ── ce qui est RÉGLABLE ────────────────────────────────────────────────
    def test_seule_la_poignee_est_un_placement_reglable(self):
        placements = self._placements()
        self.assertEqual(list(placements), ["c%s" % self.link_poignee.id])
        poignee = placements["c%s" % self.link_poignee.id]
        self.assertEqual(poignee["linkId"], self.link_poignee.id)
        self.assertEqual(poignee["label"], "Poignée")
        self.assertEqual([q["id"] for q in poignee["questions"]], [self.couleur.id])

    def test_le_rail_pilote_par_son_parent_n_apparait_pas(self):
        self.assertNotIn("c%s" % self.link_rail.id, self._placements())

    def test_la_question_a_la_forme_de_celles_de_la_racine(self):
        question = self._placements()["c%s" % self.link_poignee.id]["questions"][0]
        self.assertEqual(sorted(question), ["displayType", "id", "multi", "name", "required", "values"])
        self.assertEqual(sorted(question["values"][0]),
                         ["available", "chosen", "color", "id", "image", "name"])

    # ── RÉPONDRE ───────────────────────────────────────────────────────────
    def test_repondre_ecrit_la_session_et_coche_la_valeur(self):
        state = self.session.web_set_child_value(self.link_poignee.id, self.noir)
        self.assertEqual(self.session.child_values,
                         {str(self.link_poignee.id): {str(self.couleur.id): self.noir.id}})
        question = state["placements"]["c%s" % self.link_poignee.id]["questions"][0]
        chosen = [v["id"] for v in question["values"] if v["chosen"]]
        self.assertEqual(chosen, [self.noir.id])

    def test_la_reponse_entre_dans_la_DEFINITION_du_placement(self):
        self.session.web_set_child_value(self.link_poignee.id, self.noir)
        definition = self.session.web_state()["definition"]
        child = next(c for c in definition["children"] if c["linkId"] == self.link_poignee.id)
        self.assertEqual(child["attributeOverrides"][str(self.couleur.id)], {"value": self.noir.id})

    def test_repondre_a_ce_que_l_auteur_a_fixe_est_REFUSE(self):
        self.assertEqual(self.session.web_set_child_value(self.link_rail.id, self.courte),
                         {"error": "unknown_value"})
        self.assertFalse(self.session.child_values)

    def test_deux_placements_de_la_meme_piece_se_repondent_separement(self):
        second = self.env["product.model3d.component"].create(
            {"parent_id": self.porte.id, "child_id": self.poignee.id})
        self.session.web_set_child_value(self.link_poignee.id, self.noir)
        self.session.web_set_child_value(second.id, self.blanc)
        definition = self.session.web_state()["definition"]
        by_link = {c["linkId"]: c["attributeOverrides"].get(str(self.couleur.id))
                   for c in definition["children"]}
        self.assertEqual(by_link[self.link_poignee.id], {"value": self.noir.id})
        self.assertEqual(by_link[second.id], {"value": self.blanc.id})

    # ── la VARIANTE naît à la confirmation ─────────────────────────────────
    def test_la_variante_de_la_poignee_nait_avec_la_couleur_repondue(self):
        self.session.web_set_child_value(self.link_poignee.id, self.noir)
        self.session.write({"state": "draft"})
        self.session.web_confirm()
        born = self.session.child_variants
        self.assertIn(str(self.link_poignee.id), born)
        variant = self.env["product.product"].browse(born[str(self.link_poignee.id)])
        self.assertEqual(variant.product_tmpl_id, self.poignee_tmpl)
        self.assertEqual(variant.product_template_attribute_value_ids
                         .mapped("product_attribute_value_id"), self.noir)

    def test_sans_reponse_aucune_variante_d_enfant(self):
        self.session.web_confirm()
        self.assertFalse(self.session.child_variants)

    # ── LA VUE CAMÉRA porte sa CIBLE (D-116) ───────────────────────────────
    # Gerry (2026-09-23) : « lorsque l'on quitte [l'isolation], il faut revenir à la vue
    # caméra en cours qui donnera la target » — donc la vue servie doit la porter.
    def _camera(self, **vals):
        return self.env["product.model3d.camera"].create({
            "name": "Vue", "model3d_id": self.porte.id, "is_thumbnail": True, **vals})

    def test_la_vue_servie_vise_le_PLACEMENT_de_sa_cible(self):
        self._camera(target_kind="piece", target_link_id=self.link_poignee.id)
        self.assertEqual(self.session.web_state()["camera"]["target"],
                         {"nodeId": "c%s" % self.link_poignee.id})

    def test_la_vue_servie_vise_la_matiere_ou_l_origine(self):
        camera = self._camera(target_kind="root")
        self.assertEqual(self.session.web_state()["camera"]["target"], {"root": True})
        camera.target_kind = "origin"
        self.assertEqual(self.session.web_state()["camera"]["target"], {"origin": True})
