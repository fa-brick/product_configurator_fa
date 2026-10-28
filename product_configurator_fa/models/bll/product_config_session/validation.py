"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def validate_domains_against_sels(self, domains, value_ids=None, custom_vals=None):
        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()

        if value_ids is None:
            value_ids = self.value_ids.ids

        # process domains as shown in this wikipedia pseudocode:
        # https://en.wikipedia.org/wiki/Polish_notation#Order_of_operations
        stack = []
        for domain in reversed(domains):
            if isinstance(domain, tuple):
                # ⚠️ **UNE COMPARAISON SE LIT SUR LA RÉPONSE SAISIE**, pas sur les
                # valeurs choisies (D-267). Une question numérique n'est pas
                # répondue en cochant : sa réponse vit dans `custom_vals`, et c'est à
                # elle que la règle se compare.
                #
                # ⓘ Réponse absente ou illisible → la règle n'est pas satisfaite. C'est
                # l'inverse de la doctrine de l'éditeur 3D (D-150, « on ignore ce qu'on
                # ne sait pas »), et c'est voulu : ici la condition GOUVERNE ce qu'on
                # propose au client, et proposer sur la foi d'une réponse manquante
                # ouvrirait des questions que la règle voulait fermer.
                if domain[1] in self.env["product.config.domain.line"].NUMERIC_CONDITIONS:
                    reponse = (custom_vals or {}).get(domain[0])
                    try:
                        gauche, droite = float(reponse), float(domain[2])
                    except (TypeError, ValueError):
                        stack.append(False)
                        continue
                    verdicts = {
                        "=": gauche == droite, "!=": gauche != droite,
                        ">": gauche > droite, ">=": gauche >= droite,
                        "<": gauche < droite, "<=": gauche <= droite,
                    }
                    stack.append(verdicts[domain[1]])
                    continue
                # evaluate operand and push to stack
                if domain[1] == "in":
                    if not set(domain[2]) & set(value_ids):
                        stack.append(False)
                        continue
                else:
                    if set(domain[2]) & set(value_ids):
                        stack.append(False)
                        continue
                stack.append(True)
            else:
                # evaluate operator and previous 2 operands
                # compute_domain() only inserts 'or' operators
                # compute_domain() enforces 2 operands per operator
                operand1 = stack.pop()
                operand2 = stack.pop()
                stack.append(operand1 or operand2)

        # 'and' operator is implied for remaining stack elements
        avail = True
        while stack:
            avail &= stack.pop()
        return avail

    @api.model
    def values_available(
        self,
        check_val_ids=None,
        value_ids=None,
        custom_vals=None,
        product_tmpl_id=None,
        product_template_attribute_line_id=None,
    ):
        """Determines whether the attr_values from the product_template
        are available for selection given the configuration ids and the
        dependencies set on the product template

        :param check_val_ids: list of attribute value ids to check for
                              availability
        :param value_ids: list of attribute value ids
        :param custom_vals: custom values dict {attr_id: custom_val}

        :returns: list of available attribute values
        """
        if check_val_ids is None:
            check_val_ids = self.value_ids.ids
        elif check_val_ids:
            check_val_ids = check_val_ids.copy()
        if not self.product_tmpl_id:
            product_tmpl = self.env["product.template"].browse(product_tmpl_id)
        else:
            product_tmpl = self.product_tmpl_id

        product_tmpl.ensure_one()

        if product_template_attribute_line_id is not None:
            product_template_attribute_lines = self.env[
                "product.template.attribute.line"
            ].browse(product_template_attribute_line_id)
        else:
            product_template_attribute_lines = product_tmpl.attribute_line_ids

        if value_ids is None:
            value_ids = self.value_ids.ids
        elif value_ids:
            value_ids = value_ids.copy()

        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()

        avail_val_ids = []
        for attr_val_id in check_val_ids:
            config_lines = product_tmpl.config_line_ids.filtered(
                lambda line, attr_val_id=attr_val_id: attr_val_id in line.value_ids.ids
            )
            if product_template_attribute_lines:
                config_lines = config_lines.filtered(
                    lambda line: line.attribute_line_id
                    in product_template_attribute_lines
                )
            domains = config_lines.mapped("domain_id").compute_domain()
            avail = self.validate_domains_against_sels(domains, value_ids, custom_vals)
            if avail:
                avail_val_ids.append(attr_val_id)
            elif attr_val_id in value_ids:
                value_ids.remove(attr_val_id)

        return avail_val_ids

    def check_attributes_configuration(
        self, attribute_line_ids, custom_vals, value_ids, final=True
    ):
        for line in attribute_line_ids:
            # Validate custom values
            attr = line.attribute_id
            if attr.id in custom_vals:
                # ⚠️ La validation porte sur la LIGNE, pas sur l'attribut global
                # (D-089) — et elle reçoit la configuration courante, sans quoi
                # une borne conditionnelle n'aurait aucun moyen de se choisir.
                line.validate_custom_val(
                    custom_vals[attr.id], value_ids=value_ids, custom_vals=custom_vals
                )
            if final:
                line_values = line._configurator_value_ids()
                common_vals = set(value_ids) & set(line_values.ids)
                custom_val = custom_vals.get(attr.id)
                avail_val_ids = self.values_available(
                    check_val_ids=line_values.ids,
                    value_ids=value_ids,
                    product_tmpl_id=self.product_tmpl_id,
                    product_template_attribute_line_id=line.id,
                )
                if (
                    line.required
                    and avail_val_ids
                    and not common_vals
                    and not custom_val
                ):
                    # TODO: Verify custom value type to be correct
                    raise ValidationError(
                        self.env._("Required attribute '%s' is empty", attr.name)
                    )

    @api.model
    def validate_configuration(
        self,
        value_ids=None,
        custom_vals=None,
        product_tmpl_id=False,
        final=True,
    ):
        """Verifies if the configuration values passed via value_ids and
        custom_vals are valid

        :param value_ids: list of attribute value ids
        :param custom_vals: custom values dict {attr_id: custom_val}
        :param final: boolean marker to check required attributes.
                      pass false to check non-final configurations

        :returns: Error dict with reason of validation failure
                  or True
        """
        # TODO: Raise ConfigurationError with reason
        # Check if required values are missing for final configuration
        if value_ids is None:
            value_ids = self.value_ids.ids

        if product_tmpl_id:
            product_tmpl = self.env["product.template"].browse(product_tmpl_id)
        else:
            product_tmpl = self.product_tmpl_id

        product_tmpl.ensure_one()

        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()
        open_step_lines = self.get_open_step_lines()
        attribute_line_ids = open_step_lines.mapped("attribute_line_ids")
        attribute_line_ids += self.get_extra_attribute_line_ids(
            product_template_id=product_tmpl
        )
        # ⚠️ Un attribut masqué qui reste OBLIGATOIRE bloque la configuration
        # sans que rien ne s'affiche pour le débloquer. La visibilité doit donc
        # être tranchée AVANT l'exigence, jamais après (D-086, esprit de D-078).
        attribute_line_ids = attribute_line_ids.filtered(
            lambda line: line._is_visible(value_ids, custom_vals)
        )
        self.check_attributes_configuration(
            attribute_line_ids, custom_vals, value_ids, final=final
        )

        # Check if all the values passed are not restricted
        avail_val_ids = self.values_available(
            value_ids, value_ids, product_tmpl_id=product_tmpl_id
        )
        if set(value_ids) - set(avail_val_ids):
            restrict_val = list(set(value_ids) - set(avail_val_ids))
            product_att_values = self.env["product.attribute.value"].browse(
                restrict_val
            )
            group_by_attr = {}
            for val in product_att_values:
                if val.attribute_id in group_by_attr:
                    group_by_attr[val.attribute_id] += val
                else:
                    group_by_attr[val.attribute_id] = val

            message = self.env._("The following values are not available:")
            for attr, val in group_by_attr.items():
                message += "\n {}: {}".format(attr.name, ", ".join(val.mapped("name")))
            raise ValidationError(message)

        # Check if custom values are allowed
        custom_attr_ids = (
            product_tmpl.attribute_line_ids.filtered("custom")
            .mapped("attribute_id")
            .ids
        )
        if not set(custom_vals.keys()) <= set(custom_attr_ids):
            custom_attrs_with_error = list(
                set(custom_vals.keys()) - set(custom_attr_ids)
            )
            custom_attrs_with_error = self.env["product.attribute"].browse(
                custom_attrs_with_error
            )
            error_message = self.env._(
                "The following custom values are not permitted "
                "according to the product template - %s.\n\nIt is possible "
                "that a change has been made to allowed custom values "
                "while your configuration was in process. Please reset your "
                "current session and start over or contact your administrator"
                " in order to proceed."
            )
            message_vals = ""
            for attr_id in custom_attrs_with_error:
                message_vals += f"\n {attr_id.name}: {custom_vals.get(attr_id.id)}"
            raise ValidationError(error_message % (message_vals))

        # Check if there are multiple values passed for non-multi attributes
        mono_attr_lines = product_tmpl.attribute_line_ids.filtered(
            lambda line: not line.multi
        )
        attrs_with_error = {}
        for line in mono_attr_lines:
            if len(set(line.value_ids.ids) & set(value_ids)) > 1:
                wrong_vals = self.env["product.attribute.value"].browse(
                    set(line.value_ids.ids) & set(value_ids)
                )
                attrs_with_error[line.attribute_id] = wrong_vals
        if attrs_with_error:
            error_message = self.env._(
                "The following multi values are not permitted "
                "according to the product template - %s.\n\nIt is possible "
                "that a change has been made to allowed multi values "
                "while your configuration was in process. Please reset your "
                "current session and start over or contact your administrator"
                " in order to proceed."
            )
            message_vals = ""
            for attr_id, vals in attrs_with_error.items():
                message_vals += "\n {}: {}".format(
                    attr_id.name, ", ".join(vals.mapped("name"))
                )
            raise ValidationError(error_message % (message_vals))
        return True
