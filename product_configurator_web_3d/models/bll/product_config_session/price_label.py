"""Ce qu'exécute `product.config.session` (BLL, D-541).

Les MONTANTS que la page affiche — le supplément de chaque réponse et le total, formatés
avec leur devise (W-100, D-396).

Les nombres de `web_state` restent ce qu'ils étaient (sondes, tests, panier) ; ce module y
AJOUTE des libellés prêts à afficher, formatés au serveur dans la langue de la page.

Plan : `product_3Dmodel/_bmad-output/implementation-artifacts/plan-supplement-reponse.md`.
"""
from odoo import fields, models
from odoo.tools.misc import format_amount


# ⓘ Le signe moins typographique : « −3,00 € », et non un trait d'union.
MINUS = "\N{MINUS SIGN}"


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    # ── LA DEVISE ───────────────────────────────────────────────────────────
    def _web_currency(self):
        """La devise de l'affichage : celle de la liste de prix qui fait le total.

        ⚠️ La même liste que `get_cfg_price`, sinon la devise affichée ne serait pas celle du montant (D-092).
        """
        pricelist = self._web_pricing()[0]
        if pricelist is None:
            pricelist = self.env.user.partner_id.property_product_pricelist
        return pricelist.currency_id or self.env.company.currency_id

    def _web_amount_label(self, amount, currency=None, signed=False, suffix=""):
        """`12,50 €`, ou `+12,50 €` / `−3,00 €` quand `signed` — dans la langue du contexte."""
        currency = currency or self._web_currency()
        text = format_amount(self.env, abs(amount) if signed else amount, currency)
        if signed:
            text = ("+" if amount > 0 else MINUS) + text
        return text + suffix

    # ── LE SUPPLÉMENT DE CHAQUE RÉPONSE — W-100, lot 1 ─────────────────────
    def _web_attribute_lines(self, layout=None):
        """Chaque réponse reçoit `extra` : son supplément, déjà formaté, ou `None`.

        ⚠️ Prix CATALOGUE hors taxes, sans liste de prix : une règle peut dépendre de la combinaison entière (D-396).
        ⚠️ Aucun supplément sur une cote de grille : son prix vient de la grille, pas de la réponse (D-396, cas 4).
        """
        questions = super()._web_attribute_lines(layout=layout)
        tmpl = self.product_tmpl_id
        lines = {line.attribute_id.id: line for line in tmpl.attribute_line_ids}
        axes = {line.attribute_id.id for line in tmpl._grid_axis_lines().values()}
        currency = self._web_currency()
        surface = None
        for question in questions:
            line = lines.get(question["id"])
            extras = {}
            if line and question["id"] not in axes:
                if surface is None and line.price_mode == "per_sqm":
                    surface = self.get_config_surface(
                        self.value_ids.ids, self._get_custom_vals_dict())
                extras = self._web_value_extras(line, currency, surface or 0.0)
            for value in question["values"]:
                value["extra"] = extras.get(value["id"])
        return questions

    def _web_value_extras(self, line, currency, surface=0.0):
        """`{id de valeur: libellé}` des suppléments NON NULS d'une question — une lecture par question.

        ⚠️ Une valeur qui désigne un produit affiche le prix de CE produit : c'est lui qui entre au total (D-199).
        ⚠️ Un taux au m² sans surface connue s'affiche « /m² », sinon « +25 » se lirait vingt-cinq euros (D-161).
        """
        company = self.env.company
        today = fields.Date.context_today(self)
        out = {}
        for ptav in line.product_template_value_ids:
            value = ptav.product_attribute_value_id
            suffix, source = "", ptav.currency_id
            if value.product_id:
                product = value.product_id.sudo()
                amount, source = product.lst_price, product.currency_id
            elif line.price_mode == "per_sqm" and ptav.price_extra_sqm:
                amount = ptav.price_extra_sqm * (surface or 1.0)
                suffix = "" if surface else "/m²"
            else:
                amount = ptav.price_extra
            amount = source._convert(amount, currency, company, today, round=False)
            if currency.is_zero(amount):
                continue
            out[value.id] = self._web_amount_label(amount, currency, signed=True, suffix=suffix)
        return out

    # ── LE TOTAL AFFICHÉ — W-100, lot 2 ─────────────────────────────────────
    def web_state(self):
        """`totalLabel` : le total formaté avec sa devise, à côté du nombre `total`.

        ⚠️ Le nombre `total` reste HORS taxes : le prix de la session et la ligne de commande n'en dépendent pas (D-396).
        """
        state = super().web_state()
        state["totalLabel"] = self._web_amount_label(self._web_displayed_total(state))
        return state

    def _web_displayed_total(self, state):
        """Le total tel qu'on l'affiche : le produit, puis chaque ligne à part, chacun avec SES taxes."""
        Product = self.env["product.product"].sudo()
        Value = self.env["product.attribute.value"].sudo()
        total = self._web_displayed_price(state["price"], self.product_tmpl_id)
        for line in state.get("separateLines") or []:
            product = (Product.browse(line["productId"]) if line.get("productId")
                       else Value.browse(line["valueId"]).product_id)
            total += self._web_displayed_price(line["price"], product) * line["qty"]
        return total

    def _web_displayed_price(self, unit_price, product):
        """Le prix UNITAIRE affiché d'un article — hors taxes ici, le module boutique le taxe selon le site.

        ⚠️ Unitaire puis multiplié : une taxe fixe s'applique par unité, pas une fois par ligne.
        """
        return unit_price
