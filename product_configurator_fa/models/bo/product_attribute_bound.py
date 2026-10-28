"""Ce que déclare `product.attribute.bound` (BO, D-541)."""
from odoo import fields, models


class ProductAttributeBound(models.Model):
    """Une borne qui ne s'applique QUE si son domaine est satisfait — D-076.

    « Ligne de ressort arrière → largeur maxi 4 000 » s'écrit ici, et le domaine
    référence les valeurs par leur ENREGISTREMENT : renommer une valeur ne casse
    donc rien, par construction. C'est ce qui a rendu inutile le code technique
    que D-076 réclamait d'abord sur les valeurs.
    """
    _name = "product.attribute.bound"
    _description = "Conditional Bound of a Product Attribute Line"
    _inherit = ["product.attribute.bound.mixin"]
    _order = "sequence, id"

    attribute_line_id = fields.Many2one(
        comodel_name="product.template.attribute.line",
        string="Attribute Line",
        required=True,
        ondelete="cascade",
        index=True,
    )

    domain_id = fields.Many2one(
        comodel_name="product.config.domain",
        string="Condition",
        required=True,
        ondelete="restrict",
        help="Bounds below apply only to configurations matching this condition",
    )

    sequence = fields.Integer(
        default=10,
        help="First matching line wins, so order matters",
    )
