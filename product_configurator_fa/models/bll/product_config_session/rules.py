"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    @api.constrains("state")
    def _check_product_id(self):
        for session in self.filtered(lambda s: s.state == "done"):
            if not session.product_id:
                raise ValidationError(
                    self.env._(
                        "Finished configuration session must have a "
                        "product_id linked"
                    )
                )

    def write(self, vals):
        """Validate configuration when writing new values to session.

        ⚠️ **ET POSER LA TRACE** — D-253. Elle vit ICI et non dans une seconde
        `write` : Python garde la DERNIÈRE définition du corps de classe, et une
        surcharge ajoutée plus haut serait muette, sans une erreur.

        ⚠️ La trace est posée **après** la validation, qui peut elle-même
        retirer des valeurs devenues indisponibles : la note doit dire l'état
        où l'on ARRIVE, pas celui qu'on a demandé. D'où le drapeau de contexte,
        qui empêche l'écriture interne ci-dessous d'en produire une seconde.
        """
        trace = "value_ids" in vals and not self.env.context.get("cfg_no_trace")
        avant = (
            {record.id: record._configuration_snapshot() for record in self}
            if trace else {}
        )
        if trace:
            self = self.with_context(cfg_no_trace=True)
        res = super().write(vals)
        if not self.product_tmpl_id:
            self._trace_configuration_change(avant)
            return res
        value_ids = self.value_ids.ids
        avail_val_ids = self.values_available(value_ids)
        if set(value_ids) - set(avail_val_ids):
            self.value_ids = [(6, 0, avail_val_ids)]
        try:
            self.validate_configuration(final=False)
        except ValidationError as exc:
            raise ValidationError(self.env._(f"{exc}")) from exc
        except Exception as exc:
            raise ValidationError(self.env._("Invalid Configuration")) from exc
        self._trace_configuration_change(avant)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "product.config.session"
            ) or self.env._("New")
            product_tmpl = (
                self.env["product.template"]
                .browse(vals.get("product_tmpl_id"))
                .exists()
            )
            if product_tmpl:
                default_val_ids = (
                    product_tmpl.attribute_line_ids.filtered(
                        lambda line: line.default_val
                    )
                    .mapped("default_val")
                    .ids
                )
                # ⚠️ **UN DÉFAUT INDISPONIBLE N'EST PAS UNE RÉPONSE — on l'écarte, on ne bloque
                # pas** : des défauts incompatibles entre eux empêcheraient d'ouvrir toute
                # configuration du produit (L-433).
                default_val_ids = self._available_default_val_ids(
                    product_tmpl, default_val_ids)
                value_ids = vals.get("value_ids")
                if value_ids:
                    default_val_ids += value_ids[0][2]
                try:
                    self.validate_configuration(
                        value_ids=default_val_ids,
                        final=False,
                        product_tmpl_id=product_tmpl.id,
                    )
                    # TODO: Remove if cond when PR with
                    # raise error on github is merged
                except ValidationError as exc:
                    # ⚠️ `exc.name` n'existe plus depuis Odoo 16 : le relais lèverait une
                    # `AttributeError` et cacherait le vrai message (L-433).
                    raise ValidationError(exc.args[0] if exc.args else str(exc)) from exc
                except Exception as exc:
                    raise ValidationError(
                        self.env._(
                            "Default values provided generate an invalid "
                            "configuration"
                        )
                    ) from exc
                vals.update({"value_ids": [(6, 0, default_val_ids)]})
        sessions = super().create(vals_list)
        # ⚠️ Le jeton se pose ICI et non dans un second `create` : la classe en
        # définit déjà un, et une seconde définition du même nom écraserait la
        # première EN SILENCE — c'est Python, pas Odoo, qui tranche ([[L-141]]).
        sessions._ensure_access_token()
        return sessions
