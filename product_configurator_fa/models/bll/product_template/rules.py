"""Ce qu'exécute `product.template` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.constrains("config_ok", "attribute_line_ids")
    def _check_no_variant_lines(self):
        """W-99 / D-393 — rendre un produit configurable revérifie ses questions « sans
        variante » : la règle vit sur la ligne, ce relais la fait jouer au bon moment."""
        self.filtered("config_ok").attribute_line_ids._check_no_variant_on_configurable()

    @api.constrains("attribute_line_ids", "attribute_value_line_ids")
    def check_attr_value_ids(self):
        """Check attribute lines don't have some attribute value that
        is not present in attribute lines of that product template"""
        for product_tmpl in self:
            if not product_tmpl.env.context.get("check_constraint", True):
                continue
            attr_val_lines = product_tmpl.attribute_value_line_ids
            attr_val_ids = attr_val_lines.mapped("value_ids")
            if not attr_val_ids <= product_tmpl.attribute_line_val_ids:
                raise ValidationError(
                    self.env._(
                        "All attribute values used in attribute value lines "
                        "must be defined in the attribute lines of the "
                        "template"
                    )
                )

    @api.constrains("attribute_value_line_ids")
    def _validate_unique_config(self):
        """Check for duplicate configurations for the same
        attribute value in image lines"""
        for template in self:
            attr_val_line_vals = template.attribute_value_line_ids.read(
                ["value_id", "value_ids"], load=False
            )
            attr_val_line_vals = [
                (line["value_id"], tuple(line["value_ids"]))
                for line in attr_val_line_vals
            ]
            if len(set(attr_val_line_vals)) != len(attr_val_line_vals):
                raise ValidationError(
                    self.env._(
                        "You cannot have a duplicate configuration for the same value"
                    )
                )

    @api.constrains("config_line_ids", "attribute_line_ids")
    def _check_default_value_domains(self):
        for template in self:
            try:
                template._check_default_values()
            except ValidationError as exc:
                raise ValidationError(
                    self.env._(
                        "Restrictions added make the current default values "
                        "generate an invalid configuration.\
                      \n%s"
                    )
                    % (exc.args[0])
                ) from exc

    # ─ QB : ON PRÉVIENT, ON NE CONVERTIT NI NE REFUSE — D-200 ───────────────
    #
    # ⓘ Des exclusions sur un produit qui devient configurable : un avertissement — ni
    # conversion automatique, ni refus de la bascule (D-200).
    #
    # ⚠️ **CES EXCLUSIONS SONT DÉJÀ SANS EFFET, et c'est tout le sujet.** Le
    # configurateur ne les lit pas : aucune occurrence de `exclude_for`,
    # `_is_combination_possible` ni `_get_attribute_exclusions` dans ce module. Et
    # `_create_variant_ids` saute les produits configurables, ce qui prive les
    # exclusions de leur seul autre consommateur. L'avertissement ne change donc
    # aucun comportement : **il rend explicite un silence**. Aujourd'hui l'interface
    # laisse croire qu'un réglage agit, ce qui est pire que de ne pas l'offrir.
    #
    # ⓘ Un `onchange` et pas une contrainte : une contrainte ne sait que refuser (D-200),
    # et seul un `onchange` peut retourner `{"warning": ...}`.
    #
    # ⚠️ Corollaire à connaître : `toggle_config()` — l'ancienne action, encore
    # appelable — ne déclenche AUCUN onchange. La bascule par la case à cocher
    # avertit, la bascule par le bouton non. C'est le prix de l'avertissement, et
    # c'est aussi une raison de plus de ne garder que la case (D-186).
    @api.onchange("config_ok")
    def _onchange_config_ok_warns_about_exclusions(self):
        if not self.config_ok or not self._origin:
            return None
        tmpl_id = self._origin.id
        exclusions = self.env["product.template.attribute.exclusion"].search_count(
            [
                "|",
                ("product_tmpl_id", "=", tmpl_id),
                ("product_template_attribute_value_id.product_tmpl_id", "=", tmpl_id),
            ]
        )
        if not exclusions:
            return None
        return {
            "warning": {
                "title": self.env._("Exclusions will no longer apply"),
                "message": self.env._(
                    "This product carries %s native exclusion(s). A configurable "
                    "product does not read them: state these restrictions as "
                    "configurator conditions instead. The exclusions are left "
                    "untouched — nothing is deleted or converted.",
                    exclusions,
                ),
            }
        }

    @api.constrains("config_line_ids")
    def _check_config_line_domain(self):
        attribute_line_ids = self.attribute_line_ids
        tmpl_value_ids = attribute_line_ids._configurator_value_ids()
        tmpl_attribute_ids = attribute_line_ids.mapped("attribute_id")
        error_message = False
        for domain_id in self.config_line_ids.mapped("domain_id"):
            domain_attr_ids = domain_id.domain_line_ids.mapped("attribute_id")
            domain_value_ids = domain_id.domain_line_ids.mapped("value_ids")
            invalid_value_ids = domain_value_ids - tmpl_value_ids
            invalid_attribute_ids = domain_attr_ids - tmpl_attribute_ids
            if not invalid_attribute_ids and not invalid_value_ids:
                continue
            if not error_message:
                error_message = self.env._(
                    "Following Attribute/Value from restriction "
                    "are not present in template attributes/values. "
                    "Please make sure you are adding right restriction"
                )
            error_message += self.env._("\nRestriction: %s", domain_id.name)
            error_message += (
                invalid_attribute_ids
                and self.env._(
                    "\nAttribute/s: %s", ", ".join(invalid_attribute_ids.mapped("name"))
                )
                or ""
            )
            error_message += (
                invalid_value_ids
                and self.env._(
                    "\nValue/s: %s\n", ", ".join(invalid_value_ids.mapped("name"))
                )
                or ""
            )
        if error_message:
            raise ValidationError(error_message)

    @api.model_create_multi
    def create(self, vals_list):
        """Patch for check access rights of user(configurable products)"""
        for vals in vals_list:
            config_ok = vals.get("config_ok", False)
            if config_ok:
                self.check_config_user_access()
        return super().create(vals_list)

    def write(self, vals):
        """Patch for check access rights of user(configurable products)"""
        change_config_ok = "config_ok" in vals
        configurable_templates = self.filtered(lambda template: template.config_ok)
        if change_config_ok or configurable_templates:
            self[:1].check_config_user_access()

        return super().write(vals)

    def _check_default_values(self):
        default_val_ids = (
            self.attribute_line_ids.filtered(lambda line: line.default_val)
            .mapped("default_val")
            .ids
        )

        cfg_session_obj = self.env["product.config.session"]
        try:
            cfg_session_obj.validate_configuration(
                value_ids=default_val_ids, product_tmpl_id=self.id, final=False
            )
        except ValidationError as exc:
            raise ValidationError(exc.args[0]) from exc
        except Exception as exc:
            raise ValidationError(
                self.env._("Default values provided generate an invalid configuration")
            ) from exc

    @api.model
    def _check_config_group_rights(self):
        """Return True/False from system parameter
        - Signals access rights needs to check or not
        :Params: return : boolean"""
        ICPSudo = self.env["ir.config_parameter"].sudo()
        manager_product_configuration_settings = ICPSudo.get_param(
            "product_configurator_fa.manager_product_configuration_settings"
        )
        return manager_product_configuration_settings

    @api.model
    def check_config_user_access(self):
        """Check user have access to perform action(create/write/delete)
        on configurable products"""
        if not self._check_config_group_rights():
            return True
        config_manager = self.env.user.has_group(
            "product_configurator_fa.group_product_configurator_fa_manager"
        )
        user_root = self.env.ref("base.user_root")
        user_admin = self.env.ref("base.user_admin")
        if (
            config_manager
            or self.env.user.id in [user_root.id, user_admin.id]
            or self.env.su
        ):
            return True
        raise ValidationError(
            self.env._(
                "Sorry, you are not allowed to create/change this kind of "
                "document. For more information please contact your manager."
            )
        )
