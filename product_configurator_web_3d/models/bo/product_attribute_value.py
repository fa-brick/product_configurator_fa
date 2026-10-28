"""Ce que déclare `product.attribute.value` (BO, D-541)."""
from odoo import fields, models


class ProductAttributeValue(models.Model):
    """Une valeur peut DÉSIGNER une matière — et c'est sa miniature qui la choisit.

    ⚠️ **Le type « matière » ne désignait encore RIEN.** Il est arrivé comme un
    libellé du `Selection` ci-dessus : aucune colonne de la valeur ne pointait une
    fiche matière. Ce champ est le chaînon qui manquait.

    ⚠️ La MATIÈRE et non la teinte du nuancier (`product.model3d.color`) : une essence de
    chêne n'a pas de code hexadécimal (D-196).

    ⚠️ **La miniature n'est pas RECOPIÉE** : `material_preview` est un `related` en lecture
    seule ; une copie divergerait à la première retouche de la matière (D-196).

    ⓘ Le droit de lecture existe déjà : `product.model3d.material` est lisible par
    `base.group_user`, donc par tout utilisateur interne qui ouvre un attribut.
    """
    _inherit = "product.attribute.value"

    material_id = fields.Many2one(
        comodel_name="product.model3d.material",
        string="Material",
        # `restrict` et non `cascade` : une matière encore désignée par une valeur
        # de catalogue ne doit pas disparaître en silence — la valeur perdrait ce
        # qu'elle désigne sans que rien ne le dise.
        ondelete="restrict",
        index=True,
        help="The material this value stands for. Its preview is what the "
             "customer picks from.",
    )

    material_preview = fields.Image(
        related="material_id.preview_image",
        string="Material preview",
        readonly=True,
    )
