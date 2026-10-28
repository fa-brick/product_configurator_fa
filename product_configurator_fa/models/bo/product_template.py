"""Ce que déclare `product.template` (BO, D-541)."""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    config_ok = fields.Boolean(string="Can be Configured")

    # ─ L'ONGLET A SON PROPRE CHAMP SUR LES MÊMES LIGNES — D-209 ─────────────
    #
    # ⚠️ **UN MÊME `One2many` DÉCLARÉ DEUX FOIS DANS UN FORMULAIRE CASSE LA
    # SAUVEGARDE** : deux jeux de commandes pour les mêmes lignes lèvent *« Values must
    # belong to the attribute of the corresponding attribute_line »* (D-209).
    # ⓘ Un second champ, MÊME modèle et MÊME inverse : les mêmes enregistrements, donc le
    # même ordre (Q2), mais deux affichages — l'onglet « Attributs & Variantes » ne change
    # pas (D-209).
    configurator_line_ids = fields.One2many(
        comodel_name="product.template.attribute.line",
        inverse_name="product_tmpl_id",
        string="Configurator Attributes",
        help="The same attribute lines as the Attributes tab, shown with what "
             "the configurator needs: conditions, steps, 3D view.",
    )

    config_line_ids = fields.One2many(
        comodel_name="product.config.line",
        inverse_name="product_tmpl_id",
        string="Attribute Dependencies",
        copy=False,
    )

    config_image_ids = fields.One2many(
        comodel_name="product.config.image",
        inverse_name="product_tmpl_id",
        string="Configuration Images",
        copy=True,
    )

    attribute_value_line_ids = fields.One2many(
        comodel_name="product.attribute.value.line",
        inverse_name="product_tmpl_id",
        string="Attribute Value Lines",
        copy=True,
    )

    attribute_line_val_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        compute="_compute_template_attr_vals",
        store=False,
    )

    config_step_line_ids = fields.One2many(
        comodel_name="product.config.step.line",
        inverse_name="product_tmpl_id",
        string="Configuration Lines",
        copy=False,
    )

    # We are calculating weight of variants based on weight of
    # product-template so that no need of compute and inverse on this
    weight = fields.Float(
        compute="_compute_weight",
        inverse="_set_weight",  # pylint: disable=C8110
        search="_search_weight",
        store=False,
    )

    weight_dummy = fields.Float(
        string="Manual Weight",
        digits="Stock Weight",
        help="Manual setting of product template weight",
    )

    price_grid_ids = fields.One2many(
        comodel_name="product.price.grid",
        inverse_name="product_tmpl_id",
        string="Price Grids",
    )

    # ─ LA GRILLE SE RANGE AVEC LA LISTE DE PRIX — D-214 ─────────────────────
    #
    # ⓘ Elles ne décident PAS la même chose — la grille **produit** le prix d'un
    # produit dimensionné (D-083, D-093), la liste de prix **l'ajuste** pour un
    # client ou une quantité. Mais elles répondent à la même question de
    # l'utilisateur : *« où se règle le prix ? »*. Deux portes éloignées pour une
    # seule question, c'est une porte de trop.
    #
    # ⇒ La grille prend un bouton d'en-tête **à côté** de celui d'Odoo, et quitte
    # l'onglet du configurateur — qui ne garde que l'arbre, comme la maquette.
    price_grid_count = fields.Integer(compute="_compute_price_grid_count")
