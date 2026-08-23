from odoo.addons.base.tests.common import BaseCommon


class SessionIdentity(BaseCommon):
    """La session : jeton, filiation, traçabilité, prix — lot 5 (D-091, D-092).

    Le fil : un particulier configure, transmet à un professionnel, qui reprend
    et commande. Chacun voit SES prix, et l'original reste intact.
    """

    @classmethod
    def default_env_context(cls):
        """⚠️ `BaseCommon` COUPE le mail et le suivi par défaut
        (`DISABLED_MAIL_CONTEXT`, `odoo/addons/base/tests/common.py:58`), et sa
        docstring le dit : « To Override to reactivate the tracking ». Sans
        cette surcharge, la traçabilité que D-092 réclame se testerait toujours
        absente — et on conclurait qu'elle ne marche pas ([[L-142]]).
        """
        return {}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = cls.env["product.template"].create(
            {"name": "Shared Door", "config_ok": True, "list_price": 200}
        )
        cls.session = cls.env["product.config.session"].create(
            {"product_tmpl_id": cls.template.id, "user_id": cls.env.user.id}
        )
        cls.other_user = cls.env["res.users"].create(
            {
                "name": "Professional",
                "login": "pro@example.com",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    # ── le jeton ─────────────────────────────────────────────────────────────

    def test_01_a_session_is_born_with_a_token(self):
        self.assertTrue(self.session.access_token)
        self.assertGreater(len(self.session.access_token), 20)

    def test_02_the_token_is_not_the_session_number(self):
        """⚠️ `CS0001`, `CS0002`… est une séquence ÉNUMÉRABLE : la donner au
        visiteur laisserait lire les configurations des autres (D-091)."""
        other = self.env["product.config.session"].create(
            {"product_tmpl_id": self.template.id, "user_id": self.env.user.id}
        )
        self.assertNotEqual(self.session.access_token, other.access_token)
        self.assertNotIn(self.session.access_token, (self.session.name or ""))

    def test_03_a_session_is_found_by_its_token_only(self):
        session_obj = self.env["product.config.session"]
        self.assertEqual(
            session_obj._find_by_access_token(self.session.access_token), self.session
        )
        self.assertFalse(session_obj._find_by_access_token("CS0001"))
        self.assertFalse(session_obj._find_by_access_token(""))
        self.assertFalse(session_obj._find_by_access_token(None))

    def test_04_an_expired_link_gives_nothing(self):
        """La promesse faite au visiteur est datée, et le ménage suit la même
        échéance — nettoyer plus tôt serait un défaut visible du client."""
        self.env.cr.execute(
            "UPDATE product_config_session SET create_date = now() - interval "
            "'200 days' WHERE id = %s",
            (self.session.id,),
        )
        self.env.invalidate_all()
        self.assertFalse(
            self.env["product.config.session"]._find_by_access_token(
                self.session.access_token
            )
        )

    # ── la filiation ─────────────────────────────────────────────────────────

    def test_05_parent_id_exists_at_last(self):
        """⚠️ `get_session_search_domain` employait `parent_id` alors qu'aucun
        champ de ce nom n'existait — un défaut DORMANT, que le paramètre
        optionnel empêchait seul de tomber."""
        self.assertIn("parent_id", self.env["product.config.session"]._fields)
        domain = self.env["product.config.session"].get_session_search_domain(
            self.template.id, parent_id=self.session.id
        )
        self.assertIn(("parent_id", "=", self.session.id), domain)
        self.env["product.config.session"].search(domain)

    def test_06_taking_over_forks_the_session(self):
        mine = self.session._session_for_edit()
        self.assertEqual(mine, self.session, "ma propre session ne se duplique pas")

        theirs = self.session.with_user(self.other_user)._session_for_edit()
        self.assertNotEqual(theirs, self.session)
        self.assertEqual(theirs.parent_id, self.session)
        self.assertEqual(theirs.user_id, self.other_user)
        self.assertTrue(theirs.access_token)
        self.assertNotEqual(theirs.access_token, self.session.access_token)

    def test_07_the_original_keeps_its_version(self):
        original_values = self.session.value_ids
        fork = self.session.with_user(self.other_user)._session_for_edit()
        fork.write({"state": "draft"})
        self.assertEqual(self.session.value_ids, original_values)
        self.assertEqual(self.session.user_id, self.env.user)
        self.assertIn(fork, self.session.child_ids)

    def test_08_a_session_now_has_a_history(self):
        """Sur un objet qui passe de main en main, savoir qui a changé quoi
        n'est pas un luxe (D-092).

        ⚠️ Les messages de suivi naissent au **PRÉ-COMMIT**
        (`_track_finalize`, `mail_thread.py:538`), pas à l'écriture ni au
        flush. Un test qui ne commet jamais n'en voit aucun et conclut que le
        suivi ne marche pas ([[L-142]]).
        """
        self.assertIn("message_ids", self.env["product.config.session"]._fields)
        other = self.env["product.config.session"].create(
            {"product_tmpl_id": self.template.id, "user_id": self.env.user.id}
        )
        self.env.cr.precommit.run()
        before = len(other.message_ids)
        other.write({"parent_id": self.session.id})
        self.env.cr.precommit.run()
        other.invalidate_recordset(["message_ids"])
        self.assertGreater(len(other.message_ids), before, "la filiation se trace")
        self.assertIn(
            "parent_id", other.message_ids.mapped("tracking_value_ids.field_id.name")
        )

    def test_08bis_a_fork_says_where_it_comes_from(self):
        """⚠️ La trace passe par `_message_log` et non `message_post` : ce
        dernier EXIGE une adresse e-mail à l'auteur, et un visiteur n'en a
        pas — la fourche elle-même échouerait."""
        fork = self.session.with_user(self.other_user)._session_for_edit()
        self.assertTrue(
            any("taken over" in (m.body or "") for m in fork.message_ids),
            "la fourche dit d'où elle vient",
        )

    # ── le prix ──────────────────────────────────────────────────────────────

    def test_09_the_price_is_not_stored(self):
        """⚠️ Un prix stocké serait celui du DERNIER qui a calculé : le
        professionnel lirait le prix du particulier (D-092)."""
        field = self.env["product.config.session"]._fields["price"]
        self.assertFalse(field.store, "le prix se recalcule pour celui qui regarde")

    def test_10_the_configuration_price_knows_the_pricelist(self):
        """⚠️ OCA rendait `list_price + price_extra`, sans liste de prix — les
        options la connaissaient, le prix principal non."""
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
        full = self.session.get_cfg_price(
            pricelist=self.env["product.pricelist"].browse()
        )
        discounted = self.session.get_cfg_price(pricelist=pricelist)
        self.assertEqual(full, 200)
        self.assertAlmostEqual(discounted, 180, places=2)

    # ── le ménage ────────────────────────────────────────────────────────────

    def test_11_abandoned_sessions_are_archived_not_the_others(self):
        confirmed = self.env["product.config.session"].create(
            {
                "product_tmpl_id": self.template.id,
                "user_id": self.env.user.id,
                "state": "draft",
            }
        )
        self.env.cr.execute(
            "UPDATE product_config_session SET create_date = now() - interval "
            "'200 days' WHERE id IN %s",
            (tuple([self.session.id, confirmed.id]),),
        )
        variant = self.env["product.product"].create(
            {"name": "Some variant", "product_tmpl_id": self.template.id}
        )
        confirmed.product_id = variant
        self.env.invalidate_all()

        self.env["product.config.session"]._gc_config_sessions()

        self.assertFalse(self.session.active, "abandonnée et vieille : archivée")
        self.assertTrue(
            confirmed.active, "elle a donné une variante : on n'y touche pas"
        )
