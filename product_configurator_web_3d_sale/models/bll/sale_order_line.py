"""Ce qu'exécute `sale.order.line` (BLL, D-541).

Configurer — ou REPRENDRE — une ligne de devis dans la page 3D.

ⓘ Aucun bouton de vue n'appelle plus `reconfigure_product` : la roue dentée a quitté la
ligne, et choisir le produit ouvre le configurateur (D-259). La méthode reste, et ses
tests avec.
"""
from odoo import Command, api, models


NO_VARIANT = "product_no_variant_attribute_value_ids"


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # ── W-99 / D-393 : la ligne porte les réponses « sans variante » de SA configuration ──
    @api.model_create_multi
    def create(self, vals_list):
        # ⚠️ AVANT `super()`, pas après : la description (`name`) se calcule à la création,
        # et seulement au changement d'article ensuite. Recopiées après coup, les réponses
        # arrivaient sur la ligne mais pas dans son texte (constat du lot 7, ligne de devis).
        for vals in vals_list:
            if vals.get("config_session_id") and NO_VARIANT not in vals:
                vals[NO_VARIANT] = self._no_variant_command(vals["config_session_id"])
        return super().create(vals_list)

    def write(self, vals):
        # ⓘ `product_id` aussi : une configuration rouverte (D-371) et reconfirmée change
        # l'article de sa ligne (`_web_after_confirm`) — et peut-être ses réponses. Écrites
        # DANS le même `write` que l'article, elles entrent dans la description recalculée.
        if NO_VARIANT in vals or not ("config_session_id" in vals or "product_id" in vals):
            return super().write(vals)
        res = True
        for session, lines in self.grouped(
                lambda line: vals.get("config_session_id", line.config_session_id.id)).items():
            extra = {NO_VARIANT: self._no_variant_command(session)} if session else {}
            res &= super(SaleOrderLine, lines).write({**vals, **extra})
        return res

    def _no_variant_command(self, session_id):
        """Les réponses « sans variante » de la configuration `session_id`, prêtes à écrire.

        Depuis l'option A, elles ne sont plus dans l'article : la ligne est le SEUL endroit où
        elles vivent après la commande — description, livraison, fabrication (le cœur d'Odoo
        les passe à l'ordre de fabrication : `never_product_template_attribute_value_ids`).
        """
        session = self.env["product.config.session"].sudo().browse(session_id)
        return [Command.set(session._web_no_variant_ptav_ids())]

    def reconfigure_product(self):
        """Ouvrir la configuration 3D de cette ligne.

        Deux cas, et ils ne se ressemblent pas :

        ⓵ **La ligne a déjà une session** — on la ROUVRE, telle quelle. Aucun
        effet de bord : c'est le cas « reprendre », et il doit être aussi sûr
        qu'un lien qu'on rouvre.

        ⓶ **La ligne n'en a pas** — on en crée une, **pré-remplie des valeurs de
        la variante** de la ligne, et on l'attache. ⚠️ Le pré-remplissage n'est
        pas cosmétique : `_compute_price_unit` recalcule le prix de la ligne à
        partir de sa session dès que le lien existe. Une session
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
