"""Ce qu'exécute `product.config.step.line` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import UserError, ValidationError


class ProductConfigStepLine(models.Model):
    _inherit = "product.config.step.line"

    @api.depends(
        "config_step_id",
        "product_tmpl_id.attribute_line_ids.sequence",
        "product_tmpl_id.attribute_line_ids.config_step_id",
    )
    def _compute_attribute_line_ids(self):
        for step_line in self:
            lines = step_line.product_tmpl_id.attribute_line_ids
            step_line.attribute_line_ids = lines.filtered(
                lambda line, s=step_line: line.config_step_owner_id == s.config_step_id
            )

    # ⚠️ LA DÉPENDANCE NE PASSE PAS PAR `attribute_line_ids`, qui est CALCULÉ et
    # non stocké depuis D-202. Odoo l'a dit à chaque démarrage : *« Field
    # 'attribute_line_ids' in dependency of 'required' should be searchable. This
    # is necessary to determine which records to recompute »* — sans champ
    # cherchable, il ne sait pas remonter des lignes vers les étapes à recalculer,
    # et l'obligation d'une étape pouvait rester périmée.
    #
    # ⓘ On dépend donc de la SOURCE, exactement celle dont `attribute_line_ids`
    # est tiré : les lignes du produit, leur ordre et leurs marqueurs.
    @api.depends(
        "config_step_id",
        "product_tmpl_id.attribute_line_ids.required",
        "product_tmpl_id.attribute_line_ids.sequence",
        "product_tmpl_id.attribute_line_ids.config_step_id",
    )
    def _compute_required(self):
        for step_line in self:
            step_line.required = any(step_line.attribute_line_ids.mapped("required"))

    @api.depends(
        "config_step_id",
        "product_tmpl_id.attribute_line_ids.sequence",
        "product_tmpl_id.attribute_line_ids.config_step_id",
    )
    def _compute_sequence(self):
        for step_line in self:
            ouvreuse = step_line.product_tmpl_id.attribute_line_ids.filtered(
                lambda line, s=step_line: line.config_step_id == s.config_step_id
            ).sorted()[:1]
            step_line.sequence = ouvreuse.sequence if ouvreuse else 9999

    @api.constrains("config_step_id")
    def _check_config_step(self):
        """Prevent to add same step more than once on same product template"""
        for config_step in self:
            cfg_step_lines = config_step.product_tmpl_id.config_step_line_ids
            cfg_steps = cfg_step_lines.filtered(
                lambda line, config_step=config_step: line != config_step
            ).mapped("config_step_id")
            if config_step.config_step_id in cfg_steps:
                raise ValidationError(
                    self.env._("Cannot have a configuration step defined twice.")
                )

    def _is_visible(self, value_ids=None, custom_vals=None):
        """L'étape est-elle montrée pour cette configuration ? — D-086.

        Sans condition, oui : une étape ne se cache pas par défaut.
        """
        self.ensure_one()
        if not self.visibility_domain_id:
            return True
        session = self.env["product.config.session"]
        return session.validate_domains_against_sels(
            self.visibility_domain_id.compute_domain(),
            value_ids or [],
            custom_vals or {},
        )

    # ⓘ LA VUE 3D D'UNE ÉTAPE, par crochets (D-386) — les mêmes que sur la ligne
    # d'attribut : `view_camera_id` vient du pont, le cœur ne le connaît pas (D-075).
    def _configurator_camera_name(self):
        self.ensure_one()
        return ""

    def _configurator_camera_id(self):
        self.ensure_one()
        return False

    def _configurator_set_camera(self, camera_id):
        raise UserError(self.env._("3D views need the 3D configurator module."))
