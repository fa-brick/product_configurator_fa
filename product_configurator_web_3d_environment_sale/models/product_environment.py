# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, fields, models

#: Les états d'un devis encore modifiable — comme la réouverture d'une configuration (D-371).
OPEN_STATES = ("draft", "sent")


class ProductEnvironment(models.Model):
    _inherit = "product.environment"

    order_ids = fields.One2many("sale.order", "environment_id", string="Quotations")

    def _open_order(self):
        """Le devis EN COURS du chantier : le plus récent, brouillon ou envoyé (Q-12.4).

        ⓘ Reprendre son projet, c'est reprendre ce devis ; commandé, il libère le chantier pour un
        nouveau montage.
        """
        self.ensure_one()
        # ⓘ Ouvert par le jeton d'un devis (8.5b) : SON montage, même commandé — alors en lecture seule.
        order_id = self.env.context.get("environment_order_id")
        if order_id:
            return self.env["sale.order"].sudo().browse(order_id).exists()
        return self.env["sale.order"].sudo().search(
            [("environment_id", "=", self.id), ("state", "in", OPEN_STATES)], order="id desc", limit=1)

    def _editor_can_write(self):
        # ⚠️ Le montage d'un devis COMMANDÉ ne bouge plus : la commande engage ce qui est posé (D-371).
        order_id = self.env.context.get("environment_order_id")
        if order_id and self.env["sale.order"].sudo().browse(order_id).state not in OPEN_STATES:
            return False
        return super()._editor_can_write()

    def _montage(self):
        # ⓘ Le montage du devis en cours, sinon celui en préparation (sans devis) — jamais celui d'un
        # autre devis du même chantier (E-1).
        order = self._open_order()
        return super()._montage().filtered(lambda placement: placement.order_id == order)

    def _placement_values(self, opening_id, product, session):
        values = super()._placement_values(opening_id, product, session)
        order = self._open_order()
        if order:
            values["order_id"] = order.id
        return values

    def editor_state(self):
        state = super().editor_state()
        order = self._open_order()
        state["quote"] = {"name": order.name, "state": order.state} if order else None
        return state

    def _copy_for_order(self, order):
        """Une COPIE de ce chantier, propre au devis (O-2) : le devis la lit, son montage y passe."""
        copy = self.copy_for_site(partner=self.partner_id, project=self.project_id, name=self.name,
                                  product=self.product_tmpl_id)
        copy._portal_ensure_token()
        order.environment_placement_ids.write({"environment_id": copy.id})
        order.environment_id = copy
        return copy

    def editor_save(self, plan, wall_height=None, wall_thickness=None, start_view=False):
        """Enregistrer le plan — dans une COPIE propre au devis quand d'autres devis le lisent (8.5c, O-2).

        ⓘ *« Pousser les murs crée une copie, les autres devis ne sont pas impactés »* (Gerry) : le montage
        du devis en cours suit le plan modifié, celui des autres devis garde le plan qu'il lisait.
        """
        self.ensure_one()
        order = self._open_order()
        others = (self.sudo().order_ids - order) if order and order.state in OPEN_STATES else None
        if not others:
            return super().editor_save(plan, wall_height=wall_height, wall_thickness=wall_thickness,
                                       start_view=start_view)
        with self.env.cr.savepoint() as savepoint:
            copy = self._copy_for_order(order)
            result = copy.with_context(environment_order_id=order.id).editor_save(
                plan, wall_height=wall_height, wall_thickness=wall_thickness, start_view=start_view)
            if not result.get("ok"):
                # ⓘ Un plan refusé ne laisse ni copie ni montage déplacé.
                savepoint.rollback()
                return result
        # ⓘ Le jeton du DEVIS désigne désormais ce montage : la page ouverte par celui du chantier y passe.
        result.update(copied=True, token=order.access_token)
        return result

    @staticmethod
    def _drop_line(line):
        """Retirer la ligne d'un produit qui quitte le montage — seulement d'un devis encore modifiable."""
        if line and line.exists() and line.order_id.state in OPEN_STATES:
            line.linked_line_ids.unlink()
            line.unlink()

    def place_product(self, opening_id, product_tmpl_id):
        # ⓘ Remplacer un produit du devis retire aussi sa ligne : le devis montre ce qui est posé.
        old_line = self._montage().filtered(lambda p: p.opening_id == opening_id).order_line_id
        result = super().place_product(opening_id, product_tmpl_id)
        if "placement" in result:
            self._drop_line(old_line)
        return result

    def remove_product(self, opening_id):
        line = self._montage().filtered(lambda p: p.opening_id == opening_id).order_line_id
        result = super().remove_product(opening_id)
        if result.get("ok"):
            self._drop_line(line)
        return result

    def request_quote(self):
        """DEMANDER UN DEVIS depuis l'environnement — ou mettre à jour celui en cours (étape 8.5a).

        ⓘ Chaque configuration posée est confirmée et devient UNE ligne liée à sa session ; le montage
        part avec le devis (Q-12.2). Une configuration incomplète BLOQUE, et la réponse dit quel
        produit et quelles questions (Q-12.3).

        :returns: ``{"quote": {...}}`` ou ``{"error": code, ...}``
        """
        self.ensure_one()
        user = self.env.user
        if user._is_public():
            return {"error": "login_required"}
        montage = self._montage()
        if not montage:
            return {"error": "empty", "message": _("Place a product in a bay before asking for a quotation.")}
        missing = []
        for placement in montage.filtered("session_id"):
            session = placement.session_id.sudo()
            if session.state != "draft":
                continue
            names = session._web_missing_attributes().attribute_id.mapped("name")
            if names:
                missing.append({"openingId": placement.opening_id,
                                "productName": placement.product_tmpl_id.display_name, "questions": names})
        if missing:
            return {"error": "incomplete", "missing": missing}
        partner = self.partner_id
        if not partner:
            # ⚠️ Au back-office, le devis est celui du CLIENT : l'employé ne s'y substitue pas.
            if user._is_internal():
                return {"error": "no_customer", "message": _("Set the customer of this environment first.")}
            partner = user.partner_id
            self.sudo().partner_id = partner
        order = self._open_order() or self.env["sale.order"].sudo().create(
            {"partner_id": partner.id, "environment_id": self.id})
        # ⓘ Le jeton du devis ouvre son montage, au portail comme au back-office (8.5b).
        order._portal_ensure_token()
        Line = self.env["sale.order.line"].sudo()
        for placement in montage:
            session = placement.session_id.sudo()
            if session and session.state == "draft":
                # ⓘ La variante naît ici ; une ligne déjà là suit d'elle-même (`_web_after_confirm`).
                session.web_confirm()
            product = session.product_id if session else placement.product_tmpl_id.product_variant_id
            line = placement.order_line_id
            if not line.exists() or line.order_id != order:
                line = Line.create({"order_id": order.id, "product_id": product.id, "product_uom_qty": 1,
                                    "config_session_id": session.id or False})
                if session:
                    session._web_sync_separate_lines(line)
            placement.write({"order_id": order.id, "order_line_id": line.id})
        return {"quote": {"name": order.name, "state": order.state}}
