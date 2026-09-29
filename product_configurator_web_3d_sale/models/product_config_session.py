# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Où la configuration ATTERRIT : la ligne de devis.

C'est la moitié qui manquait — le commercial pouvait ouvrir la page depuis une
ligne, configurer, et rien ne revenait sur le devis. Le prix suivait (le lien
existait), mais la VARIANTE n'était créée que par l'assistant.
"""
from odoo import models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def _web_after_confirm(self):
        """Poser la variante née de la configuration sur la ligne qui l'attend.

        ⚠️ `sudo` : la confirmation passe par une route publique, et l'appelant
        peut être l'utilisateur *public* — celui à qui l'on a donné le lien. Ce
        qui l'autorise est le jeton, pas ses droits.

        ⚠️ **Un devis qui n'est plus en brouillon ne bouge pas.** Une commande
        confirmée porte des engagements — prix, délais, stock : y changer un
        produit parce qu'un lien traînait dans une boîte mail serait un dégât,
        pas un service.

        ⓘ Écrire `product_id` suffit : `name`, taxes et unité se recalculent
        (ce sont des champs calculés `readonly=False` depuis Odoo 17), et le
        prix suit `config_session_id.price` par `_compute_price_unit`.
        """
        res = super()._web_after_confirm()
        lines = self.env["sale.order.line"].sudo().search(
            [("config_session_id", "in", self.ids)]
        )
        for line in lines:
            if line.order_id.state not in ("draft", "sent"):
                continue
            line.product_id = line.config_session_id.product_id
            # ⓘ D-368 — les pièces VENDUES À PART, sur leurs lignes rattachées. Seulement pour
            # une confirmation venue du LIEN : le dialogue du devis les pose lui-même dans
            # le formulaire qu'il tient (`cfg_client_lines`), sinon elles seraient doublées.
            if not self.env.context.get("cfg_client_lines"):
                line.config_session_id._web_sync_separate_lines(line)
        return res

    def _web_sync_separate_lines(self, line):
        """Remplacer les lignes rattachées de `line` par celles de la configuration — D-368.

        ⚠️ **Remplacer, jamais empiler** : une reconfiguration retire les anciennes. Ce sont
        celles de la configuration — un produit configurable n'a pas d'autre ligne rattachée
        par ce chemin.
        """
        self.ensure_one()
        line.linked_line_ids.unlink()
        for separate in self.web_separate_lines():
            if not separate["productId"]:
                continue
            self.env["sale.order.line"].sudo().create({
                "order_id": line.order_id.id,
                "product_id": separate["productId"],
                "product_uom_qty": separate["qty"],
                "linked_line_id": line.id,
            })

    def _quote_lines(self):
        return self.env["sale.order.line"].sudo().search([("config_session_id", "=", self.id)])

    def _web_reopen_if_open_quote(self):
        """Rouvrir la configuration tant que TOUTES ses lignes sont dans un devis — D-371.

        ⓘ **Rien n'est joué au stade du devis** (Gerry) : c'est la COMMANDE qui engage la
        variante. Un devis brouillon ou envoyé se corrige ; une commande confirmée (ou
        verrouillée) garde sa configuration close, comme D-190 le voulait pour elle.

        ⚠️ **Sans ligne de devis, rien ne se rouvre** : une configuration confirmée ailleurs
        (la boutique) n'a pas de devis qui la porte, et son panier ne suivrait pas.

        ⓘ **Une pièce dont la ligne a été SUPPRIMÉE du devis est désélectionnée** (Gerry) :
        rouvrir le configurateur montre ce que le devis porte. Seulement pour une
        configuration CONFIRMÉE — tant qu'elle ne l'est pas, ses lignes rattachées n'existent
        pas encore, et leur absence ne dit rien.
        """
        self.ensure_one()
        lines = self._quote_lines()
        if not lines or any(l.order_id.state not in ("draft", "sent") or l.order_id.locked
                            for l in lines):
            return False
        if self.state != "done":
            return False
        self._web_drop_removed_separate_answers(lines)
        self.write({"state": "draft"})
        # ⓘ Rouverte, elle repart sans conducteur : la main se prend au premier geste.
        self._release_hand()
        return True

    def _web_drop_removed_separate_answers(self, lines):
        """Désélectionner une pièce vendue à part dont la ligne a disparu du devis — D-371.

        ⓘ La question retombe sur son défaut s'il ne désigne aucune pièce (« Sans bumper »),
        sinon elle reste sans réponse. Une question vendue à part n'est jamais obligatoire
        (garde de la ligne d'attribut) : la laisser vide est permis.
        """
        apart = self.product_tmpl_id._sale_separately_attribute_ids()
        if not apart:
            return
        present = lines.linked_line_ids.product_id.product_tmpl_id
        dropped = self.value_ids.filtered(
            lambda v: v.attribute_id.id in apart and v.product_id
            and v.product_id.product_tmpl_id not in present)
        if not dropped:
            return
        kept = self.value_ids - dropped
        for attribute in dropped.attribute_id:
            ptal = self.product_tmpl_id.attribute_line_ids.filtered(
                lambda l, a=attribute: l.attribute_id == a)[:1]
            default = ptal.default_val if "default_val" in ptal._fields else False
            if default and not default.product_id:
                kept |= default
        self.write({"value_ids": [(6, 0, kept.ids)]})
