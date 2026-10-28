"""Ce que déclare `product.attribute.custom.value` (BO, D-541)."""
from odoo import models


class ProductAttributeCustomValue(models.Model):
    """La valeur numérique qui a quitté la session pour la VARIANTE.

    ⚠️ Le cœur d'Odoo affiche « Largeur: 2400 » et perd l'unité que la session
    savait montrer (`product_config.py`, `_compute_val_name`) : la même valeur
    se lisait donc avec son unité pendant la configuration et sans elle sur le
    devis. Une seule règle, partout — la valeur est le nombre, l'affichage
    porte l'unité.
    """
    _inherit = "product.attribute.custom.value"
