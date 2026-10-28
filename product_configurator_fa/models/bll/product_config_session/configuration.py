"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
from collections.abc import Iterable
from itertools import chain
from odoo import api, fields, models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def action_confirm(self, product_id=None):
        for session in self:
            if product_id is None:
                product_id = session.create_get_variant()
            session.write({"state": "done", "product_id": product_id.id})
        return True

    def get_custom_value_id(self):
        """Return record set of attribute value 'custom'"""
        custom_ext_id = "product_configurator_fa.custom_attribute_value"
        custom_val_id = self.env.ref(custom_ext_id)
        return custom_val_id

    @api.model
    def _get_custom_vals_dict(self):
        """Retrieve session custom values as a dictionary of the form
        {attribute_id: parsed_custom_value}"""
        custom_vals = {}
        for val in self.custom_value_ids:
            if val.attribute_id.custom_type in ["float", "integer"]:
                # ⚠️ `parse_number`, plus `literal_eval` : la seconde refuse « 2,5 »
                # et faisait tomber toute la lecture de la session ([[L-218]]). Un
                # nombre illisible reste une CHAÎNE, que la validation refuse avec
                # un message — jamais une absence, qui retomberait sur le défaut.
                number = val.attribute_id.parse_number(val.value)
                custom_vals[val.attribute_id.id] = (
                    number if number is not None else val.value
                )
            elif val.attribute_id.custom_type == "binary":
                custom_vals[val.attribute_id.id] = val.attachment_ids
            else:
                custom_vals[val.attribute_id.id] = val.value
        return custom_vals

    def flatten_attribute_value_ids(self, value_ids):
        return chain.from_iterable(
            v if isinstance(v, Iterable) else [v] for v in value_ids
        )

    def update_config(self, attr_val_dict=None, custom_val_dict=None):
        """Update the session object with the given value_ids and custom values.

        Use this method instead of write in order to prevent incompatible
        configurations as this removed duplicate values for the same attribute.

        :param attr_val_dict: Dictionary of the form {
            int (attribute_id): attribute_value_id OR [attribute_value_ids]
        }

        :custom_val_dict: Dictionary of the form {
            int (attribute_id): {
                'value': 'custom val',
                OR
                'attachment_ids': {
                    [{
                        'name': 'attachment name',
                        'datas': base64_encoded_string
                    }]
                }
            }
        }

        """
        if attr_val_dict is None:
            attr_val_dict = {}
        if custom_val_dict is None:
            custom_val_dict = {}
        update_vals = {}

        value_ids = self.value_ids.ids
        for attr_id, vals in attr_val_dict.items():
            attr_val_ids = self.value_ids.filtered(
                lambda x, attr_id=attr_id: x.attribute_id.id == int(attr_id)
            ).ids
            # Remove all values for this attribute and add vals from dict
            value_ids = list(set(value_ids) - set(attr_val_ids))
            if not vals:
                continue
            if isinstance(vals, list):
                value_ids += vals
            elif isinstance(vals, int):
                value_ids.append(vals)

        if value_ids != self.value_ids.ids:
            update_vals.update({"value_ids": [(6, 0, value_ids)]})

        # Remove all custom values included in the custom_vals dict
        self.custom_value_ids.filtered(
            lambda x: x.attribute_id.id in custom_val_dict.keys()
        ).unlink()

        if custom_val_dict:
            binary_field_ids = (
                self.env["product.attribute"]
                .search(
                    [
                        ("id", "in", list(custom_val_dict.keys())),
                        ("custom_type", "=", "binary"),
                    ]
                )
                .ids
            )
        else:
            binary_field_ids = []

        for attr_id, vals in custom_val_dict.items():
            if not vals:
                continue

            if "custom_value_ids" not in update_vals:
                update_vals["custom_value_ids"] = []

            custom_vals = {"attribute_id": attr_id}

            if attr_id in binary_field_ids:
                attachments = [
                    (
                        0,
                        0,
                        {"name": val.get("name"), "datas": val.get("datas")},
                    )
                    for val in vals
                ]
                custom_vals.update({"attachment_ids": attachments})
            else:
                custom_vals.update({"value": vals})

            update_vals["custom_value_ids"].append((0, 0, custom_vals))
        self.write(update_vals)

    def _resolve_custom_vals(self, value_ids, custom_vals):
        """Range les saisies en valeurs d'attribut — D-081, étendu au texte par D-353.

        Rend les `value_ids` augmentés. La session, elle, n'est PAS modifiée :
        elle garde la saisie en clair, qui est la trace de ce que le client a
        tapé, et le seul enregistrement neuf est celui qu'exige la variante.

        ⓘ **C'est ICI, à la confirmation, que la valeur naît** — et pas avant
        (D-353) : une configuration abandonnée ne laisse rien au catalogue.
        """
        self.ensure_one()
        resolved = list(value_ids or [])
        for line in self.product_tmpl_id.attribute_line_ids:
            attribute = line.attribute_id
            if attribute.id not in (custom_vals or {}):
                continue
            if not attribute._resolves_to_values():
                continue
            value = line.resolve_custom_value(custom_vals[attribute.id])
            if value and value.id not in resolved:
                resolved.append(value.id)
        return resolved

    # TODO: Should be renamed to get_active_step_line
    @api.model
    def get_open_step_lines(self, value_ids=None):
        """
        Returns a recordset of configuration step lines open for access given
        the configuration passed through value_ids

        e.g: Field A and B from configuration step 2 depend on Field C
        from configuration step 1. Since fields A and B require action from
        the previous step, configuration step 2 is deemed closed and redirect
        is made for configuration step 1.

        :param value_ids: list of value.ids representing the
                          current configuration
        :returns: recordset of accesible configuration steps
        """

        if value_ids is None:
            value_ids = self.value_ids.ids

        open_step_lines = self.env["product.config.step.line"]

        for cfg_line in self.product_tmpl_id.config_step_line_ids:
            # ⚠️ La condition EXPLICITE tranche avant l'effet de bord : une
            # étape masquée par sa condition ne s'ouvre pas, même si ses
            # attributs ont des valeurs disponibles (D-086).
            if not cfg_line._is_visible(value_ids):
                continue
            for attr_line in cfg_line.attribute_line_ids:
                available_vals = self.values_available(
                    attr_line.value_ids.ids,
                    value_ids,
                    product_template_attribute_line_id=attr_line.id,
                )
                # TODO: Refactor when adding restriction to custom values
                if available_vals or attr_line.custom:
                    open_step_lines |= cfg_line
                    break

        return open_step_lines.sorted()

    @api.model
    def get_extra_attribute_line_ids(self, product_template_id):
        """Retrieve attribute lines defined on the product_template_id
        which are not assigned to configuration steps"""

        extra_attribute_line_ids = (
            product_template_id.attribute_line_ids
            - product_template_id.config_step_line_ids.mapped("attribute_line_ids")
        )
        return extra_attribute_line_ids

    @api.model
    @api.model
    def _available_default_val_ids(self, product_tmpl, val_ids):
        """Les valeurs PAR DÉFAUT qui restent disponibles ensemble — les autres s'écartent."""
        if not val_ids:
            return val_ids
        available = set(self.values_available(
            check_val_ids=val_ids, value_ids=val_ids, custom_vals={},
            product_tmpl_id=product_tmpl.id))
        return [v for v in val_ids if v in available]

    # TODO: Disallow duplicates
    def flatten_val_ids(self, value_ids):
        """Return a list of value_ids from a list with a mix of ids
        and list of ids (multiselection)

        :param value_ids: list of value ids or mix of ids and list of ids
                           (e.g: [1, 2, 3, [4, 5, 6]])
        :returns: flattened list of ids ([1, 2, 3, 4, 5, 6])"""
        if not isinstance(value_ids, list | tuple):
            return [value_ids]  # Ensure single values are wrapped in a list

        flat_val_ids = set(self.flatten_attribute_value_ids(value_ids))
        return list(flat_val_ids)

    @api.model
    def get_child_specification(self, model, parent):
        """return dictiory of onchange specification by
        appending parent before each key"""
        model_obj = self.env[model]
        specs = model_obj._onchange_spec()
        new_specs = {}
        for key, val in specs.items():
            new_specs[f"{parent}.{key}"] = val
        return new_specs

    @api.model
    def get_onchange_specifications(self, model):
        """return onchange specification
        - same functionality by _onchange_spec
        - needed this method because odoo don't add specification for fields
        one2many or many2many there is view-reference(using : tree_view_ref)
        intead of view in that field"""
        if not model:
            return {}
        model_obj = self.env.get(model)
        specs = model_obj._onchange_spec()
        for name, field in model_obj._fields.items():
            if field.type not in ["one2many", "many2many"]:
                continue
            ch_specs = self.get_child_specification(
                model=field.comodel_name, parent=name
            )
            specs.update(ch_specs)
        return specs

    @api.model
    def get_vals_to_write(self, values, model):
        """Return values in formate excepted by write/create methods
        - same functionality by _convert_to_write
        - needed this method because odoo don't call convert to write
        for the many2many/one2many fields"""
        model_obj = self.env[model]
        values = model_obj._convert_to_write(values)
        fields = model_obj._fields
        for key, vals in values.items():
            if not isinstance(vals, list):
                continue
            new_lst = []
            for line in vals:
                new_line = line
                if line and isinstance(line[-1], dict):
                    new_line = line[:-1] + (
                        self.get_vals_to_write(
                            values=line[-1], model=fields[key].comodel_name
                        ),
                    )
                new_lst.append(new_line)
            values[key] = new_lst
        return values
