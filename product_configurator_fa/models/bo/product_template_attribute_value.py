"""Ce que déclare `product.template.attribute.value` (BO, D-541)."""
from odoo import fields, models


class ProductAttributePrice(models.Model):
    _inherit = "product.template.attribute.value"

    # Leverage product.template.attribute.value to compute the extra weight
    # each attribute adds
    weight_extra = fields.Float(string="Attribute Weight Extra", digits="Stock Weight")

    # Exposé pour les VUES seulement : le mode vit sur la ligne, mais c'est la
    # valeur qu'on édite, et une colonne ne peut pas se cacher sur un champ
    # qu'elle ne porte pas.
    price_mode = fields.Selection(
        related="attribute_line_id.price_mode", string="Extra Price Mode", readonly=True
    )

    # ─ LA CORBEILLE A DEUX VISAGES — B4, QC, D-205 ──────────────────────────
    #
    # ⓘ Supprimer tant qu'aucune variante n'existe, désactiver sinon — et le DIRE avant
    # le clic, par l'avertissement de `_onchange_values_warns_about_deactivation`.
    # ⓘ `removal_effect` n'est plus montré en colonne (D-205, amendé) : le champ reste.
    #
    # ⚠️ **LE CŒUR LE FAIT DÉJÀ.** `ProductTemplateAttributeValue.unlink()`
    # supprime, et **archive quand il ne peut pas** — sa docstring le dit :
    # *« Archive the value if unlink is not possible »*. Ce lot n'ajoute donc
    # aucun comportement : il ajoute la seule chose qui manquait, **dire ce que le
    # clic va faire avant qu'il le fasse**. Un bouton, deux effets, décidés par un
    # état que l'utilisateur ne voit pas : sans cela, le même geste détruit ici et
    # masque là.
    #
    # ⚠️ **C'est une PRÉVISION, pas une promesse.** Le cœur enveloppe sa
    # suppression dans un `try/except Exception` large : une contrainte qu'on ne
    # sait pas anticiper peut encore la faire basculer en archivage. On annonce
    # donc l'archivage quand on le SAIT, jamais la suppression comme certaine.
    removal_effect = fields.Selection(
        selection=[("delete", "Delete"), ("archive", "Deactivate")],
        compute="_compute_removal_effect",
        string="On removal",
        help="What removing this value would do. Deactivating keeps past orders "
             "valid while taking the choice out of future configurations.",
    )

    # ⚠️ LA MÊME RÈGLE SUR L'ÉCRAN DU PRODUIT (D-199). Une valeur qui désigne un
    # produit y montrait son `price_extra` — un montant que le calcul IGNORE, le
    # prix du produit prenant sa place. Masquer la colonne du catalogue sans faire
    # ce geste ici n'aurait pas supprimé le mensonge : il se serait déplacé.
    #
    # ⓘ Miroirs nécessaires : une vue n'évalue que les champs qu'elle porte, jamais
    # `attribute_id.value_type` (précédent du core, `display_type`).
    value_type = fields.Selection(
        related="attribute_id.value_type", string="Value Type", readonly=True
    )

    product_price = fields.Float(
        related="product_attribute_value_id.product_price",
        string="Product Price",
        readonly=True,
    )

    currency_id = fields.Many2one(
        related="product_attribute_value_id.currency_id", readonly=True
    )

    price_extra_sqm = fields.Float(
        string="Extra Price per m²",
        digits="Product Price",
        help="Rate applied to the surface of the product (grid axis X × axis Y) "
        "when the attribute line is priced per square meter",
    )
