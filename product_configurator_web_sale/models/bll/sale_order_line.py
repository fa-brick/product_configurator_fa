"""Ce qu'exécute `sale.order.line` (BLL, D-541).

Le titre d'une ligne configurée au panier : la première ligne de sa description — D-555.
Le lien qui rouvre sa configuration depuis le panier — D-556.
"""
from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.depends("product_id.display_name", "name")
    def _compute_name_short(self):
        """La première ligne de la description, sans la référence interne ; le panier écrit les suivantes dessous.

        ⚠️ Pas le nom de variante d'Odoo : ses réponses entre parenthèses doubleraient la liste écrite dessous (D-555).
        ⓘ Une ligne écrite avant D-555 garde son titre d'alors : c'est la première ligne de sa description.
        """
        super()._compute_name_short()
        for line in self:
            if not line.product_id.config_ok or not line.name:
                continue
            title = line.name.split("\n", 1)[0]
            code = line.product_id.default_code
            if code and title.startswith(f"[{code}] "):
                title = title[len(code) + 3:]
            line.name_short = title

    def _configurator_edit_url(self):
        """Le lien qui rouvre la configuration de cette ligne, ou `False` — D-556.

        ⓘ `sudo` : le visiteur n'a aucun droit sur les sessions ; le jeton est son seul accès, comme sur la page.
        ⚠️ Rien pour une commande confirmée : sa configuration ne se rouvre plus (D-371).
        """
        self.ensure_one()
        session = self.sudo().config_session_id
        if not session.access_token or self.order_id.state != "draft":
            return False
        return f"/configurator/{session.access_token}"
