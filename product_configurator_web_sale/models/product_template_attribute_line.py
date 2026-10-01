# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class ProductTemplateAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"

    def _prepare_single_value_for_display(self):
        """Le tableau d'informations d'un produit configurable ne répète pas ses QUESTIONS.

        Odoo y range tout attribut dont la ligne n'a qu'une valeur, qu'il crée des
        variantes ou non (« Type de TopPlate : Classic » sur la fiche du JeNo) : pour un
        produit configurable, c'est une question du configurateur, réglée là-bas. Seuls
        restent les attributs « sans variante » — une information pure (une matière, une
        gamme), qui ne se choisit pas (Gerry, 2026-10-01 — W-69, Q6).

        ⚠️ **En Python, et non par `xpath`** : `website_sale_comparison` REMPLACE le bloc
        `#product_attributes_simple`, et un `xpath` sur lui dépendrait de l'ordre
        d'application des vues. Et du Python n'est pas soumis aux copies de vue d'un site
        figées par l'éditeur ([[L-356]]) : il vaut partout dès la mise à jour du module.

        ⓘ La comparaison lit aussi cette méthode pour ses spécifications : elle en suit la
        règle. Ses lignes à plusieurs valeurs et son bouton « Comparer », eux, restent
        (Gerry, Q4) — ils passent par `_prepare_categories_for_display`, intouché.

        ⓘ Filtré PAR LIGNE avant `super()` : un recordset peut mêler plusieurs produits, et
        le type rendu (`OrderedDict`, que les gabarits itèrent) reste celui d'Odoo.
        """
        kept = self.filtered(
            lambda line: not line.product_tmpl_id.config_ok
            or line.attribute_id.create_variant == "no_variant"
        )
        return super(ProductTemplateAttributeLine, kept)._prepare_single_value_for_display()
