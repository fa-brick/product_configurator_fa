"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def create_get_variant(self, value_ids=None, custom_vals=None):
        """Creates a new product variant with the attributes passed
        via value_ids and custom_values or retrieves an existing
        one based on search result

            :param value_ids: list of product.attribute.values ids
            :param custom_vals: dict {product.attribute.id: custom_value}

            :returns: new/existing product.product recordset

        """
        if self.product_tmpl_id.config_ok:
            self.validate_configuration()
        if value_ids is None:
            value_ids = self.value_ids.ids

        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()

        try:
            self.validate_configuration()
        except ValidationError as exc:
            raise ValidationError(exc.args[0] if exc.args else str(exc)) from exc
        except Exception as exc:
            raise ValidationError(self.env._("Invalid Configuration")) from exc

        # La saisie libre devient une VALEUR d'attribut ici, et pas avant :
        # une configuration abandonnée ne doit rien laisser derrière elle
        # (D-082). C'est ce qui rend la variante distinguable en stock (D-081).
        value_ids = self._resolve_custom_vals(value_ids, custom_vals)

        duplicates = self.search_variant(
            value_ids=value_ids, product_tmpl_id=self.product_tmpl_id
        )
        if duplicates:
            return duplicates[:1]

        vals = self.get_variant_vals(value_ids, custom_vals)
        product_obj = (
            self.env["product.product"].sudo().with_context(mail_create_nolog=True)
        )
        variant = product_obj.sudo().create(vals)

        variant.message_post(
            body=self.env._("Product created via configuration wizard"),
            author_id=self.env.user.partner_id.id,
        )

        return variant

    def _get_config_image(self, value_ids=None, custom_vals=None, size=None):
        """
        Retreive the image object that most closely resembles the configuration
        code sent via value_ids list

        The default image object is the template (self)
        :param value_ids: a list representing the ids of attribute values
                         (usually stored in the user's session)
        :param custom_vals: dictionary of custom attribute values
        :returns: path to the selected image
        """
        # TODO: Also consider custom values for image change
        if value_ids is None:
            value_ids = self.value_ids.ids

        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()

        img_obj = self.product_tmpl_id
        max_matches = 0
        value_ids = self.flatten_val_ids(value_ids)
        for line in self.product_tmpl_id.config_image_ids:
            matches = len(set(line.value_ids.ids) & set(value_ids))
            if matches > max_matches:
                img_obj = line
                max_matches = matches
        return img_obj

    def get_config_image(self, value_ids=None, custom_vals=None, size=None):
        """
        Retreive the image object that most closely resembles the configuration
        code sent via value_ids list
        For more information check _get_config_image
        """
        config_image_id = self._get_config_image(
            value_ids=value_ids, custom_vals=custom_vals
        )
        return config_image_id.image_1920

    @api.model
    def get_variant_vals(self, value_ids=None, custom_vals=None, **kwargs):
        """Hook to alter the values of the product variant before creation

        :param value_ids: list of product.attribute.values ids
        :param custom_vals: dict {product.attribute.id: custom_value}

        :returns: dictionary of values to pass to product.create() method
        """
        self.ensure_one()

        if value_ids is None:
            value_ids = self.value_ids.ids

        if custom_vals is None:
            custom_vals = self._get_custom_vals_dict()

        image = self.get_config_image(value_ids)
        value_ids = self._variant_value_ids(value_ids)
        ptav_ids = self.env["product.template.attribute.value"].search(
            [
                ("product_tmpl_id", "=", self.product_tmpl_id.id),
                ("product_attribute_value_id", "in", value_ids),
            ]
        )
        vals = {
            "product_tmpl_id": self.product_tmpl_id.id,
            "product_template_attribute_value_ids": [(6, 0, ptav_ids.ids)],
            "taxes_id": [(6, 0, self.product_tmpl_id.taxes_id.ids)],
            "image_1920": image,
        }
        return vals

    @api.model
    def get_variant_search_domain(self, product_tmpl_id, value_ids=None):
        """Method called by search_variant used to search duplicates in the
        database"""

        if value_ids is None:
            value_ids = self.value_ids.ids

        value_ids = self._variant_value_ids(value_ids, product_tmpl_id)
        domain = [
            ("product_tmpl_id", "=", product_tmpl_id.id),
            ("config_ok", "=", True),
        ]
        pta_value_ids = self.env["product.template.attribute.value"].search(
            [
                ("product_tmpl_id", "=", product_tmpl_id.id),
                ("product_attribute_value_id", "in", value_ids),
            ]
        )
        for value_id in pta_value_ids:
            domain.append(("product_template_attribute_value_ids", "=", value_id.id))
        return domain

    @api.model
    def _variant_value_ids(self, value_ids, product_tmpl_id=None):
        """Les valeurs qui entrent dans la VARIANTE — celles des questions qui CRÉENT des variantes.

        ⚠️ **La règle du cœur d'Odoo (W-99 / D-393, option A)** : une valeur `no_variant` dans
        la variante ferait recomposer au panier d'Odoo un AUTRE article, sans la réponse, et
        la fiche boutique ne rendrait plus son formulaire. Une réponse « sans variante » va
        sur la LIGNE de commande (`product_no_variant_attribute_value_ids`), jamais dans
        l'article.

        ⓘ Ce qui le rend sûr pour la fabrication : un produit configurable n'a plus le droit de
        poser une question « sans variante » qui désigne un COMPOSANT intégré
        (`_check_no_variant_on_configurable`) — la nomenclature est bâtie par article.

        ⓘ D-368 : une question vendue à part est « sans variante » par construction ; elle
        sort donc d'ici sans règle à part. Sa pièce a sa propre ligne.
        """
        values = self.env["product.attribute.value"].browse(value_ids)
        return [v.id for v in values if v.attribute_id.create_variant != "no_variant"]

    def search_variant(self, value_ids=None, product_tmpl_id=None):
        """Searches product.variants with given value_ids and custom values
        given in the custom_vals dict

        :param value_ids: list of product.attribute.values ids
        :param custom_vals: dict {product.attribute.id: custom_value}

        :returns: product.product recordset of products matching domain
        """
        if value_ids is None:
            value_ids = self.value_ids.ids

        custom_value_id = self.get_custom_value_id()
        value_ids = list(set(value_ids) - set(custom_value_id.ids))

        if not product_tmpl_id:
            product_tmpl_id = self.product_tmpl_id
            if not product_tmpl_id:
                raise ValidationError(
                    self.env._(
                        "Cannot conduct search on an empty config session "
                        "without product_tmpl_id kwarg"
                    )
                )
        # ⓘ AVANT le comptage d'en bas : une variante n'a pas de valeur vendue à part.
        value_ids = self._variant_value_ids(value_ids, product_tmpl_id)

        domain = self.get_variant_search_domain(
            product_tmpl_id=product_tmpl_id, value_ids=value_ids
        )
        products = self.env["product.product"].search(domain)

        # At this point, we might have found products with all of the passed
        # in values, but it might have more attributes!  These are NOT
        # matches
        more_attrs = products.filtered(
            lambda p: len(p.product_template_attribute_value_ids) != len(value_ids)
        )
        products -= more_attrs
        return products
