"""Poser une étape depuis l'arbre — D-212.

⚠️ **UNE ÉTAPE S'OUVRE SUR UN ATTRIBUT, elle ne flotte pas.** C'est la
contrepartie de la forme (A) retenue avec Gerry (D-202) : l'étape est un
*marqueur* porté par la ligne qui l'ouvre, et non une ligne à elle seule. Ajouter
une étape, c'est donc **désigner la ligne à partir de laquelle elle commence**.

ⓘ D'où cet assistant plutôt qu'un bouton muet : il faut deux informations —
quelle étape, et à partir d'où. Un bouton qui devinerait « la dernière ligne »
serait juste une fois sur deux.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ConfiguratorAddStep(models.TransientModel):
    _name = "product.configurator.add.step"
    _description = "Add a configuration step from the tree"

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template", required=True, readonly=True
    )
    config_step_id = fields.Many2one(
        comodel_name="product.config.step", string="Step", required=True
    )
    attribute_line_id = fields.Many2one(
        comodel_name="product.template.attribute.line",
        string="Starts at",
        required=True,
        help="The step opens on this attribute: it and everything below belong "
             "to it, until another step opens.",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        template = self.env["product.template"].browse(
            self.env.context.get("default_product_tmpl_id")
        )
        # ⓘ On propose la PREMIÈRE ligne encore libre : c'est là qu'une étape
        # neuve commence le plus souvent, et cela évite de couper une étape
        # existante en deux par inadvertance.
        libre = template.attribute_line_ids.sorted().filtered(
            lambda ligne: not ligne.config_step_id
        )[:1]
        if libre:
            values.setdefault("attribute_line_id", libre.id)
        return values

    def action_apply(self):
        self.ensure_one()
        if self.attribute_line_id.product_tmpl_id != self.product_tmpl_id:
            # ⚠️ Le domaine de la vue le filtre déjà ; ceci est la barrière qui ne
            # dépend pas de l'interface (D-080).
            raise UserError(
                _("This attribute line does not belong to this product.")
            )
        self.attribute_line_id.config_step_id = self.config_step_id
        return {"type": "ir.actions.act_window_close"}
