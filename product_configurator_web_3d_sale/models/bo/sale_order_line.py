"""Ce que déclare `sale.order.line` (BO, D-541)."""
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # ── CE QUE LE CLIENT DOIT SAVOIR AVANT DE CHOISIR — D-259 ────────────────
    #
    # ⚠️ Le drapeau suit le MODÈLE, jamais `product_id` : pour un produit configurable,
    # la VARIANTE n'existe pas encore au moment du choix (D-259).
    #
    # ⓘ Un `related` plutôt qu'un aller-retour de plus : le widget lit la donnée
    # déjà chargée avec la ligne, sans appeler le serveur pour chaque produit.
    product_tmpl_config_ok = fields.Boolean(
        related="product_template_id.config_ok",
        string="Configurable template",
        readonly=True,
    )
