"""Ce qu'exécute `product.config.domain.line` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductConfigDomainLine(models.Model):
    _inherit = "product.config.domain.line"

    #: Comparaisons à un NOMBRE (D-267). Elles portent sur la réponse SAISIE d'une question
    #: numérique (`custom_vals`), là où `in`/`not in` portent sur des valeurs choisies.
    NUMERIC_CONDITIONS = ("=", "!=", ">", ">=", "<", "<=")

    @api.depends("attribute_id")
    def _compute_template_attribute_value_ids(self):
        for domain in self:
            domain.template_attribute_value_ids = (
                domain._get_allowed_attribute_value_ids()
            )

    def _compute_attribute_id_domain(self):
        if "product_attribute_ids" in self.env.context:
            return [("id", "in", self.env.context["product_attribute_ids"][0][2])]
        return []

    def _get_domain_conditions(self):
        operators = [("in", "In"), ("not in", "Not In")]
        # ⚠️ **UNE COMPARAISON N'EST PAS UNE APPARTENANCE**, et le stockage les
        # distingue par le champ qu'elles remplissent : `value_ids` pour l'une,
        # `numeric_value` pour l'autre. Les mêlant, `in` sur un nombre ou `>` sur des
        # valeurs auraient produit des règles qu'aucun évaluateur ne sait lire.
        operators += [
            ("=", "="), ("!=", "\u2260"),
            (">", ">"), (">=", "\u2265"), ("<", "<"), ("<=", "\u2264"),
        ]
        return operators

    def _get_domain_operators(self):
        andor = [("and", "And"), ("or", "Or")]

        return andor

    @api.constrains("condition", "value_ids", "product_ids", "attribute_id")
    def _check_numeric_leaf(self):
        """Une comparaison porte sur une question NUMÉRIQUE, et sur rien d'autre.

        ⓘ Sans ce refus, `épaisseur > 4` posée sur une question de couleur serait
        stockée puis évaluée contre une réponse qui n'est pas un nombre : la règle
        serait simplement fausse, toujours, sans que rien ne le dise.
        """
        for line in self:
            if line.condition not in self.NUMERIC_CONDITIONS:
                continue
            if line.value_ids or line.product_ids:
                raise ValidationError(self.env._(
                    "A comparison rule compares a number: it cannot also list values."))
            if not line.attribute_id.is_numeric():
                raise ValidationError(self.env._(
                    "“%(attribute)s” is not a numeric question: compare it to values, "
                    "not to a number.", attribute=line.attribute_id.name))

    @api.constrains("attribute_id", "value_ids", "product_ids")
    def _check_leaf_form(self):
        """Une ligne désigne des valeurs OU des produits — jamais les deux.

        ⚠️ `value_ids` était `required` ; il ne peut plus l'être, sinon la forme
        « produit » serait impossible à enregistrer. Cette garde REMPLACE cette
        obligation : sans elle, une ligne vide passerait — et une condition vide
        n'exclut rien, en silence.

        ⚠️ **`attribute_id` est dans la liste EXPRÈS, et c'est le piège.** Odoo
        ne déclenche une contrainte que pour les champs RÉELLEMENT écrits : une
        ligne qui ne mentionne ni valeurs ni produits ne touchait aucun des deux
        champs surveillés, et passait donc **sans être vérifiée** — exactement le
        cas que cette garde existe pour attraper. `attribute_id` étant
        obligatoire, il est toujours présent à la création.
        """
        for line in self:
            # ⓘ **UNE COMPARAISON NE DÉSIGNE RIEN** (D-267) : elle compare la
            # réponse saisie à un nombre. Sa garde à elle est `_check_numeric_leaf`,
            # qui exige une question numérique et refuse justement les valeurs.
            if line.condition in self.NUMERIC_CONDITIONS:
                continue
            if bool(line.value_ids) == bool(line.product_ids):
                raise ValidationError(
                    self.env._(
                        "A condition line must designate either values or "
                        "products, not both and not neither."
                    )
                )

    @api.onchange("attribute_id")
    def _onchange_attribute_purge_leaf(self):
        """Changer d'attribut vide la feuille — les deux formes.

        ⚠️ Sans cela, la ligne gardait les valeurs de l'attribut PRÉCÉDENT :
        `_resolved_value_ids` renvoyait des valeurs étrangères à l'attribut
        testé, et la condition ne pouvait plus être vraie. Le même piège que la
        purge des produits à la bascule de `value_type`.
        """
        self.value_ids = False
        self.product_ids = False

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._materialise_designated()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if "product_ids" in vals or "attribute_id" in vals:
            self._materialise_designated()
        return res

    def _get_allowed_attribute_value_ids(self):
        self.ensure_one()
        product_template = self.env["product.template"]
        if self.env.context.get("product_tmpl_id"):
            product_template = product_template.browse(
                self.env.context.get("product_tmpl_id")
            )
        template_lines = product_template.attribute_line_ids
        attribute_values = self.attribute_id._configurator_value_ids()
        return (
            product_template
            and (template_lines._configurator_value_ids() & attribute_values)
            or attribute_values
        )

    def _resolved_value_ids(self):
        """Les valeurs que cette ligne teste — quelle que soit sa forme.

        ⚠️ **LE SEUL POINT OÙ LES DEUX FORMES SE REJOIGNENT.** Tout ce qui lit
        une condition passe par ici : l'évaluation, le résumé en pastilles, le
        rendu vers l'éditeur. Une lecture qui prendrait `value_ids` en direct
        verrait une feuille « produit » comme VIDE — donc un `in` qui ne matche
        jamais et un `not in` qui matche toujours, en silence.
        """
        valeurs = self.env["product.attribute.value"]
        for line in self:
            if line.product_ids:
                # ⓘ Les valeurs existent : elles sont matérialisées à
                # l'enregistrement de la ligne (voir `_materialise_designated`),
                # jamais ici — évaluer une condition ne doit rien écrire.
                valeurs |= line.attribute_id.value_ids.filtered(
                    lambda v, line=line: v.product_id in line.product_ids
                )
            else:
                valeurs |= line.value_ids
        return valeurs

    def _materialise_designated(self):
        """Donne une valeur à chaque produit désigné — au moment de l'écriture.

        ⓘ Même geste que le filtre dynamique (D-222), et pour la même raison :
        l'évaluation doit rester une LECTURE. Matérialiser à la volée aurait
        écrit en base au milieu d'une configuration, y compris en lecture seule.
        """
        for line in self.filtered("product_ids"):
            line.attribute_id._materialise_products(line.product_ids)
