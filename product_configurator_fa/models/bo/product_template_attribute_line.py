"""Ce que déclare `product.template.attribute.line` (BO, D-541)."""
from odoo import fields, models


class ProductAttributeLine(models.Model):
    # ⚠️ Avec un `_inherit` en LISTE, `_name` cesse d'être déduit : sans cette
    # ligne, Odoo prend le nom de la CLASSE pour nom de modèle et refuse de
    # démarrer (`models.py:143`).
    _name = "product.template.attribute.line"
    # ⓘ Le mixin de bornes vient désormais de `product_attribute_advanced`, qui le
    # définit : le déclarer ici suffit à l'appliquer, sans le posséder.
    _inherit = ["product.template.attribute.line", "product.attribute.bound.mixin"]
    _order = "product_tmpl_id, sequence, id"

    # ⓘ `custom` a MIGRÉ vers `product_attribute_advanced` : c'est lui qui décide,
    # dans l'éditeur 3D, entre une liste déroulante et un champ de saisie.
    required = fields.Boolean(help="Is this attribute required?")

    multi = fields.Boolean(
        help="Allow selection of multiple values for this attribute?",
    )

    # ⓘ `default_val` a MIGRÉ vers `product_attribute_advanced`. L'éditeur 3D en a
    # besoin : ses réponses ne s'enregistrent pas, donc ce qui part en base — la
    # vignette, le prix — doit se construire sur le défaut du produit.
    sequence = fields.Integer(default=10)

    # ─ L'ÉTAPE EST UN SÉPARATEUR — B1, D-202 ────────────────────────────────
    #
    # ⚠️ **CE CHAMP NE DIT PAS « J'APPARTIENS À », IL DIT « J'OUVRE ».** L'étape
    # cesse d'être un contenant qui liste ses attributs : elle devient un
    # séparateur, et **ce qui suit lui appartient jusqu'au suivant**. Une ligne
    # sans marqueur hérite donc de l'étape ouverte au-dessus d'elle.
    #
    # ⓘ Pourquoi porté par la LIGNE et non par une ligne-séparateur à part, comme
    # les sections d'un devis : `product_template_attribute_line.attribute_id` est
    # **NOT NULL en base** (vérifié : `is_nullable = NO`). Aucune règle d'interface
    # ne lève ce plancher — une ligne sans attribut ne peut pas exister (D-202). Un
    # bandeau pourra venir SANS toucher au modèle, l'appartenance restant déduite de
    # la position.
    #
    # ⚠️ L'ORDRE DEVIENT UNE DONNÉE PORTEUSE. Glisser une ligne change son étape,
    # en silence. C'est le prix du séparateur, et c'est pourquoi l'étape à laquelle
    # une ligne appartient est CALCULÉE et montrée (`config_step_owner_id`) plutôt
    # que laissée à deviner.
    config_step_id = fields.Many2one(
        comodel_name="product.config.step",
        string="Opens Step",
        ondelete="restrict",
        help="When set, this line OPENS that configuration step: it and every "
             "line below belong to the step, until another line opens the next "
             "one.",
    )

    config_step_owner_id = fields.Many2one(
        comodel_name="product.config.step",
        string="Belongs to step",
        compute="_compute_config_step_owner_id",
        help="The step this line belongs to — the last one opened at or above it.",
    )

    dimension_role = fields.Selection(
        selection=[
            ("axis_x", "Grid axis X (columns)"),
            ("axis_y", "Grid axis Y (rows)"),
        ],
        string="Dimension Role",
        help="What this dimension is FOR, as opposed to what it is called. "
        "The price grid is indexed by these two roles, and the surface used "
        "by per-square-meter extras is their product.",
    )

    price_mode = fields.Selection(
        selection=[("fixed", "Fixed amount"), ("per_sqm", "Per square meter")],
        default="fixed",
        required=True,
        string="Extra Price Mode",
        help="How the extra price of this attribute's values is read on this "
        "product: a flat amount, or a rate per square meter",
    )

    # ⓘ VIDE = COMME L'ATTRIBUT (D-168) : la ligne ne décide que si on la règle.
    unavailable_display = fields.Selection(
        selection=[("grey", "Greyed out"), ("hide", "Hidden")],
        string="Unavailable values",
        help="Overrides the attribute's setting for this product only. Empty: "
        "the attribute's setting applies.",
    )

    # ─ VENDUE À PART — D-368, option B ──────────────────────────────────────
    #
    # ⓘ Le couple PRODUIT + QUESTION porte la nature commerciale d'une option : le même
    # bumper est consommé par un produit et vendu à part avec un autre. C'est ce qui ferme
    # le point ouvert de D-109. La pièce, elle, reste dans l'assemblage 3D (permutation,
    # présence, positions) : c'est la QUESTION qui dit comment elle se vend.
    sale_separately = fields.Boolean(
        string="Sold separately",
        help="The product each answer designates goes on its OWN quotation line, linked to "
        "this product's line — outside this product's price, variant and bill of "
        "materials. Requires a question whose values designate products, and that "
        "creates no variant.",
    )

    sale_separately_warning = fields.Char(
        compute="_compute_sale_separately_warning",
        string="Sold separately — warning",
    )

    visibility_domain_id = fields.Many2one(
        comodel_name="product.config.domain",
        string="Visibility Condition",
        ondelete="restrict",
        help="This attribute is asked only when the condition matches. "
        "Empty means always asked.",
    )

    bound_ids = fields.One2many(
        comodel_name="product.attribute.bound",
        inverse_name="attribute_line_id",
        string="Conditional Bounds",
        copy=True,
        help="Bounds that replace the ones above when their condition matches. "
        "The first matching line wins.",
    )

    # Exposé pour les vues seulement : le type vit sur l'attribut, mais c'est la
    # ligne qu'on édite, et un champ absent de la vue ne peut pas la conditionner.
    attribute_custom_type = fields.Selection(
        related="attribute_id.custom_type", string="Field Type", readonly=True
    )
