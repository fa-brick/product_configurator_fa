"""Ce que déclare `product.config.domain.line` (BO, D-541)."""
from odoo import fields, models


class ProductConfigDomainLine(models.Model):
    _name = "product.config.domain.line"
    _description = "Domain Line for Config Restrictions"
    _order = "sequence"

    template_attribute_value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        string="Template Attribute Values",
        compute="_compute_template_attribute_value_ids",
    )

    attribute_id = fields.Many2one(
        comodel_name="product.attribute",
        string="Attribute",
        required=True,
        domain=lambda self: self._compute_attribute_id_domain(),
    )

    domain_id = fields.Many2one(
        comodel_name="product.config.domain",
        required=True,
        string="Rule",
        # ⚠️ **SANS `cascade`, RÉÉCRIRE UNE CONDITION EST IMPOSSIBLE.** Un
        # `many2one` OBLIGATOIRE sur un modèle ordinaire vaut `restrict` par
        # défaut (`fields.py`, « 3 cases ») ; le côté `one2many` lit cette
        # politique pour décider quoi faire d'une ligne retirée, et sans
        # `cascade` il la DÉTACHE — `SET domain_id = NULL` sur une colonne qui
        # l'interdit. Le vider (`Command.CLEAR`) échouait donc toujours, et
        # supprimer une condition qui porte des règles aussi.
        #
        # ⓘ `cascade` dit ce qui est vrai : une règle appartient à sa condition
        # et n'existe pas sans elle.
        ondelete="cascade",
    )

    condition = fields.Selection(selection="_get_domain_conditions", required=True)

    value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        relation="product_config_domain_line_attr_rel",
        column1="line_id",
        column2="attribute_id",
        string="Values",
    )

    # ─ LA SECONDE FORME DE FEUILLE : DÉSIGNER DES PRODUITS — C4, D-201 ──────
    #
    # ⓘ Les conditions portent sur les valeurs d'attribut ET sur les produits : les deux
    # formes COEXISTENT, celle-ci n'en remplace aucune (D-201).
    #
    # ⚠️ **Pourquoi une seconde forme est nécessaire.** Sur un attribut à valeurs
    # dynamiques, les valeurs n'existent qu'APRÈS avoir été proposées ou
    # retenues : sans cette forme, une règle serait **impossible à écrire** tant
    # que le catalogue de valeurs est vide. Désigner le produit, lui, se fait
    # toujours.
    #
    # ⓘ L'ÉVALUATION RESTE UNIQUE : une feuille « produit » se résout en valeurs
    # au moment de l'évaluation (`_resolved_value_ids`). Un seul moteur, deux
    # formes de stockage — sinon `validate_domains_against_sels` aurait dû
    # apprendre un second vocabulaire, et les deux se seraient écartés.
    product_ids = fields.Many2many(
        comodel_name="product.product",
        relation="product_config_domain_line_product_rel",
        column1="line_id",
        column2="product_id",
        string="Products",
        help="Designate the products directly instead of their attribute "
             "values. Useful on attributes with dynamic values, whose values "
             "do not exist until they have been offered.",
    )

    attribute_value_type = fields.Selection(
        related="attribute_id.value_type",
        string="Attribute value type",
    )

    # ⚠️ **L'OPÉRANDE D'UNE COMPARAISON** — un nombre, jamais une valeur d'attribut.
    # Une question numérique ne se répond pas en choisissant dans une liste : sa réponse
    # est saisie (`custom_vals`), et c'est à elle que la règle se compare.
    numeric_value = fields.Float(
        string="Number",
        digits=(16, 4),
        help="The number this rule compares the answer to. Only for the comparison "
             "operators; membership rules use values instead.",
    )

    operator = fields.Selection(
        selection="_get_domain_operators",
        string="Operators",
        default="and",
        required=True,
    )

    sequence = fields.Integer(
        default=1,
        help="Set the order of operations for evaluation domain lines",
    )
