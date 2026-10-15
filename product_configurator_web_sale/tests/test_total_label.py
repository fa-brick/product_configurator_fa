"""Le TOTAL de la page, avec sa devise, TTC ou HT selon le site — W-100, lot 2 (D-396).

Ce qui est éprouvé : `totalLabel` de `web_state` — hors taxes hors du site, taxé quand le
site est réglé TTC, la position fiscale appliquée, chaque ligne à part taxée par SES taxes —
et le nombre `total`, qui reste hors taxes.
"""
import json

from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools.misc import format_amount


def _tax_group(env):
    """⚠️ Un groupe À SOI : sur une base dont la société n'a pas de groupe par défaut, la taxe refuse de naître."""
    return env["account.tax.group"].create({"name": "TVA W-100", "company_id": env.company.id})


@tagged("post_install", "-at_install")
class TestTotalLabel(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Tax = cls.env["account.tax"]
        group = _tax_group(cls.env)
        cls.tax_21, cls.tax_6 = Tax.create([
            {"name": "TVA 21 W-100", "amount": 21.0, "amount_type": "percent",
             "type_tax_use": "sale", "company_id": cls.env.company.id,
             "tax_group_id": group.id},
            {"name": "TVA 6 W-100", "amount": 6.0, "amount_type": "percent",
             "type_tax_use": "sale", "company_id": cls.env.company.id,
             "tax_group_id": group.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Caisse W-100", "config_ok": True, "list_price": 100.0,
            "taxes_id": [Command.set(cls.tax_21.ids)],
        })
        cls.part = cls.env["product.product"].create({
            "name": "Poignée W-100", "list_price": 10.0,
            "taxes_id": [Command.set(cls.tax_6.ids)],
        })
        # ⚠️ UNE LISTE DE PRIX À SOI : celle de la base porte parfois des règles ([[L-453]]).
        cls.pricelist = cls.env["product.pricelist"].create({"name": "Sans règle W-100"})
        cls.env.user.partner_id.specific_property_product_pricelist = cls.pricelist
        cls.env.user.partner_id.property_account_position_id = False
        cls.website = cls.env.ref("website.default_website")
        cls.currency = cls.pricelist.currency_id

    def _session(self, on_site, tax="tax_included"):
        self.website.show_line_subtotals_tax_selection = tax
        session = self.env["product.config.session"].create({
            "product_tmpl_id": self.tmpl.id, "user_id": self.env.user.id,
        })
        if on_site:
            session = session.with_context(cfg_on_site=True, website_id=self.website.id)
        return session

    def _label(self, amount):
        return format_amount(self.env, amount, self.currency)

    def test_hors_du_site_le_total_reste_HT(self):
        state = self._session(on_site=False).web_state()
        self.assertEqual(state["totalLabel"], self._label(100.0))

    def test_sur_un_site_TTC_le_total_est_taxe_mais_le_nombre_reste_HT(self):
        state = self._session(on_site=True).web_state()
        self.assertEqual(state["totalLabel"], self._label(121.0))
        self.assertEqual(state["total"], 100.0)

    def test_sur_un_site_HT_le_total_n_est_pas_taxe(self):
        state = self._session(on_site=True, tax="tax_excluded").web_state()
        self.assertEqual(state["totalLabel"], self._label(100.0))

    def test_la_position_fiscale_du_client_s_applique(self):
        fpos = self.env["account.fiscal.position"].create({
            "name": "Réduite W-100",
            "tax_ids": [Command.create({"tax_src_id": self.tax_21.id,
                                        "tax_dest_id": self.tax_6.id})],
        })
        self.env.user.partner_id.property_account_position_id = fpos
        state = self._session(on_site=True).web_state()
        self.assertEqual(state["totalLabel"], self._label(106.0))

    def test_chaque_ligne_a_part_est_taxee_par_SES_taxes(self):
        """Le produit à 21 %, la poignée à 6 % : 121 + 2 × 10,60 = 142,20."""
        session = self._session(on_site=True)
        state = {"price": 100.0, "separateLines": [
            {"productId": self.part.id, "valueId": False, "price": 10.0, "qty": 2}]}
        self.assertAlmostEqual(session._web_displayed_total(state), 142.2)


@tagged("post_install", "-at_install")
class TestTotalLabelRoute(HttpCase):
    """Le drapeau `site` de la page, par la route publique, comme un visiteur."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tax = cls.env["account.tax"].create({
            "name": "TVA 21 W-100", "amount": 21.0, "amount_type": "percent",
            "type_tax_use": "sale", "company_id": cls.env.company.id,
            "tax_group_id": _tax_group(cls.env).id})
        tmpl = cls.env["product.template"].create({
            "name": "Caisse W-100", "config_ok": True, "list_price": 100.0,
            "taxes_id": [Command.set(tax.ids)],
        })
        website = cls.env.ref("website.default_website")
        website.show_line_subtotals_tax_selection = "tax_included"
        pricelist = cls.env["product.pricelist"].create({"name": "Sans règle W-100"})
        website.user_id.partner_id.specific_property_product_pricelist = pricelist
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": tmpl.id, "user_id": cls.env.user.id,
        })
        cls.session._ensure_access_token()

    def _state(self, **params):
        response = self.url_open(
            "/configurator/state",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": dict(
                token=self.session.access_token, **params)}),
            headers={"Content-Type": "application/json"},
        )
        return response.json()["result"]

    @staticmethod
    def _digits(label):
        # ⓘ Les chiffres seuls : la route parle la langue du visiteur, pas celle du test.
        return "".join(char for char in label if char.isdigit())

    def test_la_page_du_site_recoit_le_total_TAXE(self):
        self.assertEqual(self._digits(self._state(site=True)["totalLabel"]), "12100")

    def test_sans_le_drapeau_le_total_reste_HT(self):
        """Le dialogue du devis appelle la même route, sans `site`."""
        self.assertEqual(self._digits(self._state()["totalLabel"]), "10000")
