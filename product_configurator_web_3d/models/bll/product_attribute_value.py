"""Ce qu'exécute `product.attribute.value` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    # ─ LA LIGNE SE REMPLIT SEULE — D-198 ────────────────────────────────────
    #
    # ⚠️ La miniature suivait déjà (elle est `related`) ; le NOM, non — et il est
    # requis. Choisir « Chêne » obligeait à retaper « Chêne » pour pouvoir
    # enregistrer. Le pendant exact de ce que le cœur fait pour le produit.
    #
    # Le nom personnalisé n'est jamais écrasé : voir le commentaire du cœur.
    @api.onchange("material_id")
    def _onchange_material_id_fills_the_name(self):
        if not self.material_id:
            return
        ancien = self._origin.material_id.display_name if self._origin.material_id else False
        if not self.name or self.name == ancien:
            self.name = self.material_id.display_name

    # ─ DEUX BARRIÈRES, comme partout ailleurs (D-080, D-194, D-196) ─────────
    @api.constrains("material_id")
    def _check_material_only_for_material_type(self):
        for value in self:
            if value.material_id and value.attribute_id.value_type != "material":
                raise ValidationError(
                    self.env._(
                        "Only an attribute whose values designate a Material can "
                        "point at one. Change the attribute's value type, or "
                        "clear the material."
                    )
                )

    def _web_categories(self):
        """Les catégories sous lesquelles cette réponse se range au panneau de choix — D-382.

        Une liste de `{key, name, sequence, parent}`, la FEUILLE seulement : ici la catégorie
        de la MATIÈRE que la valeur désigne (un arbre depuis D-382, dans `product_editor`).
        La boutique y ajoute les catégories e-commerce du PRODUIT désigné, par surcharge
        (`product_configurator_web_sale`) : ce module ne dépend pas de `website_sale`.

        ⚠️ Clé PRÉFIXÉE par le modèle (`m5`) : deux modèles, deux séquences d'identifiants.
        Lu en `sudo`, comme le reste de l'état : le visiteur n'a aucun droit sur les matières.
        """
        self.ensure_one()
        category = self.sudo().material_id.category_id
        if not category:
            return []
        return [{
            "key": "m%s" % category.id,
            "name": category.name,
            "sequence": category.sequence,
            "parent": category.parent_id.name or "",
        }]

    def _preview_source(self):
        """La MATIÈRE complète la chaîne du module attribut — D-258.

        ⓘ Elle vient en DERNIER, et c'est voulu : l'image posée sur la valeur,
        puis le produit qu'elle désigne, puis seulement le rendu de sa matière.
        Une valeur ne désigne jamais les deux à la fois (D-219 les efface l'une
        l'autre), donc l'ordre ne tranche rien en pratique — il dit simplement
        que ce module AJOUTE une provenance sans déplacer les autres.
        """
        record, field = super()._preview_source()
        if record:
            return record, field
        if self.material_id and self.material_id.preview_image:
            return self.material_id, "preview_image"
        return None, None

    def _purge_designation(self, value_type):
        """Le crochet du cœur, complété : la matière s'efface aussi — D-219.

        ⓘ Chaque module efface ce qu'il a posé. Le cœur ne peut pas nommer
        `material_id` : il pointe une fiche de l'éditeur, dont le cœur ne dépend pas.
        """
        super()._purge_designation(value_type)
        if value_type != "material":
            self.filtered("material_id").material_id = False
