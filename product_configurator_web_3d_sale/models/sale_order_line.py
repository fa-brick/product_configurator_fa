# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Configurer — ou REPRENDRE — depuis une ligne de devis (arbitrage Gerry, 2026-09-05).

Le bouton existe déjà : la roue dentée que `product_configurator_fa_sale` pose
sur chaque ligne configurable d'un devis en brouillon. Comme la clé à molette de
la fiche produit, il ne change ni de place ni d'icône — seulement de
destination.
"""
from odoo import Command, api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # ── W-99 / D-393 : la ligne porte les réponses « sans variante » de SA configuration ──

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sync_no_variant_from_session()
        return lines

    def write(self, vals):
        res = super().write(vals)
        # ⓘ `product_id` aussi : une configuration rouverte (D-371) et reconfirmée change
        # l'article de sa ligne (`_web_after_confirm`) — et peut-être ses réponses.
        if "config_session_id" in vals or "product_id" in vals:
            self._sync_no_variant_from_session()
        return res

    def _sync_no_variant_from_session(self):
        """Recopier sur la ligne les réponses « sans variante » de sa configuration.

        Depuis l'option A, elles ne sont plus dans l'article : la ligne est le SEUL endroit où
        elles vivent après la commande — description, livraison, fabrication (le cœur d'Odoo
        les passe à l'ordre de fabrication : `never_product_template_attribute_value_ids`).
        ⓘ N'écrit que si elles changent : pas de boucle avec `write`.
        """
        for line in self.filtered("config_session_id"):
            ptav_ids = line.config_session_id.sudo()._web_no_variant_ptav_ids()
            if set(ptav_ids) != set(line.product_no_variant_attribute_value_ids.ids):
                line.product_no_variant_attribute_value_ids = [Command.set(ptav_ids)]

    def reconfigure_product(self):
        """Ouvrir la configuration 3D de cette ligne.

        Deux cas, et ils ne se ressemblent pas :

        ⓵ **La ligne a déjà une session** — on la ROUVRE, telle quelle. Aucun
        effet de bord : c'est le cas « reprendre », et il doit être aussi sûr
        qu'un lien qu'on rouvre.

        ⓶ **La ligne n'en a pas** — on en crée une, **pré-remplie des valeurs de
        la variante** de la ligne, et on l'attache. ⚠️ Le pré-remplissage n'est
        pas cosmétique : `_compute_price_unit` recalcule le prix de la ligne à
        partir de `config_session_id.price` dès que le lien existe. Une session
        vide mettrait donc la ligne **à zéro**, sans un mot.

        ⚠️ **`force_create=True` ici**, contrairement à la fiche produit : une
        session attachée à une ligne lui appartient. Réutiliser la dernière
        session brouillon du commercial rattacherait à cette ligne-ci une
        configuration déjà portée par une autre.
        """
        self.ensure_one()
        session = self.config_session_id
        if not session:
            session = self.env["product.config.session"].create_get_session(
                self.product_id.product_tmpl_id.id, force_create=True,
            )
            # ⓘ W-99 / D-393 — et les réponses « sans variante », qui vivent sur la LIGNE
            # depuis l'option A, plus dans l'article.
            values = self.product_id.product_template_attribute_value_ids \
                | self.product_no_variant_attribute_value_ids
            session.value_ids = [(6, 0, values.product_attribute_value_id.ids)]
            self.config_session_id = session
        return session.action_open_3d_page()

    # ── CE QUE LE CLIENT DOIT SAVOIR AVANT DE CHOISIR — D-259 ────────────────
    #
    # ⚠️ `config_ok` existe déjà sur la ligne, mais il suit `product_id` : pour un
    # produit configurable, la VARIANTE n'existe pas encore au moment du choix, et
    # ce champ vaut donc `False` exactement quand on aurait besoin de lui.
    # Celui-ci suit le MODÈLE, qui est ce que le commercial vient de choisir.
    #
    # ⓘ Un `related` plutôt qu'un aller-retour de plus : le widget lit la donnée
    # déjà chargée avec la ligne, sans appeler le serveur pour chaque produit.
    product_tmpl_config_ok = fields.Boolean(
        related="product_template_id.config_ok",
        string="Configurable template",
        readonly=True,
    )
