"""Ce qu'exécute `product.template` (BLL, D-541)."""
from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def copy(self, default=None):
        """Copy restrictions, config Steps and attribute lines
        ith product template"""
        if not default:
            default = {}
        self = self.with_context(check_constraint=False)
        res = super().copy(default=default)

        # Attribute lines
        attribute_line_dict = {}
        for line in res.attribute_line_ids:
            attribute_line_dict.update({line.attribute_id.id: line.id})

        # Restrictions
        for line in self.config_line_ids:
            old_restriction = line.domain_id
            new_restriction = old_restriction.copy()
            config_line_default = {
                "product_tmpl_id": res.id,
                "domain_id": new_restriction.id,
            }
            new_attribute_line_id = attribute_line_dict.get(
                line.attribute_line_id.attribute_id.id, False
            )
            if not new_attribute_line_id:
                continue
            config_line_default.update({"attribute_line_id": new_attribute_line_id})
            line.copy(config_line_default)

        # ─ Config steps ────────────────────────────────────────────────────
        #
        # ⚠️ L'APPARTENANCE N'EST PLUS À RECOPIER (D-202) : elle est déduite de
        # l'ordre, et les lignes d'attribut de la copie portent déjà leurs
        # marqueurs — donc les étapes de la copie sont déjà DÉCLARÉES quand on
        # arrive ici. Recopier la ligne d'étape violerait l'unicité
        # `(produit, étape)`. Ce qui reste à reporter, c'est ce que la ligne
        # d'étape porte EN PROPRE : sa condition de visibilité.
        step_line_obj = self.env["product.config.step.line"]
        for line in self.config_step_line_ids:
            jumelle = step_line_obj.search([
                ("product_tmpl_id", "=", res.id),
                ("config_step_id", "=", line.config_step_id.id),
            ], limit=1)
            if jumelle:
                jumelle.visibility_domain_id = line.visibility_domain_id
            else:
                # Une étape que plus aucune ligne n'ouvre sur la copie : on la
                # garde tout de même, pour ne pas perdre ses réglages.
                line.copy({"product_tmpl_id": res.id})
        return res
