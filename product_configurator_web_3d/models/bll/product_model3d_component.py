"""Ce qu'exécute `product.model3d.component` (BLL, D-541).

La condition d'un EMPLACEMENT s'écrit dans le dialogue du configurateur — D-267.

⚠️ **POURQUOI ICI, ET NULLE PART AILLEURS.** L'éditeur 3D est LGPL-3 et ne peut pas
dépendre du configurateur, qui est AGPL-3 (D-075) : il porte le stockage de la
condition et le moteur qui l'évalue, mais pas de quoi l'écrire. Le configurateur, lui,
porte l'éditeur — le dialogue des filtres de la barre de recherche (D-087, D-203) — et
ne connaît pas les assemblages. Ce module voit les deux : c'est le seul endroit où la
jonction peut se faire.

⚠️ **UN SEUL VOCABULAIRE, ET C'EST UNE CHANCE.** Les deux côtés nomment un attribut
`__attribute_<id>` — `ATTRIBUTE_SCOPE_PREFIX` chez l'éditeur, `ATTRIBUTE_FIELD_PREFIX`
chez le configurateur — et comparent des IDENTIFIANTS de valeurs, jamais des libellés
(D-080). Une feuille d'éditeur `('__attribute_25', 'in', [12, 13])` est mot pour mot la
clause que le moteur lit. La traduction est donc une correspondance, pas une
interprétation.

─ LE ET / OU ─────────────────────────────────────────────────────────────────────

ⓘ Le OU entre DEUX questions — `montage in [...] OU hauteur in [...]` — devient un
GROUPE `{"any": [...]}` ; entre valeurs d'une même question, il reste UNE feuille `in [...]`.

⚠️ `A OU (B ET C)` est REFUSÉ par `_parse_condition_groups`, avec la phrase qui dit
pourquoi : aucun des deux stockages ne sait le garder (D-267).

ⓘ **Les comparaisons numériques passent** (`épaisseur > 4`), des deux côtés : le
modèle-sujet décrit une question numérique en `float`, la ligne de condition du
configurateur porte un `numeric_value`, et notre moteur les évaluait déjà (D-080). Une
question numérique se répond en SAISISSANT : c'est cette réponse que la comparaison lit.
"""
from odoo import _, api, models
from odoo.exceptions import UserError


class ProductModel3DComponent(models.Model):
    _inherit = "product.model3d.component"

    def action_edit_condition(self):
        """Ouvre le dialogue de condition SUR CET EMPLACEMENT (surcharge le refus poli).

        ⓘ Le produit de référence est celui de l'assemblage PARENT : c'est lui qui
        déclare les questions (D-163), et l'assistant vérifie déjà qu'une condition ne
        teste pas un attribut étranger au produit.
        """
        self.ensure_one()
        produit = self.parent_id.product_tmpl_id
        if not produit:
            raise UserError(_(
                "This assembly is not linked to a product yet: a condition tests the "
                "questions of a product."))
        return self.env["product.configurator.condition"].open_for_component(self, produit)

    def customer_answers_ordered(self):
        """Oui si une question VENDUE À PART permute ce lien — D-368.

        ⓘ La réponse du client sur cette pièce part alors avec la variante de sa propre ligne
        de devis. Sinon, la pièce est INTÉGRÉE, et son choix n'atteint pas la variante du
        produit tant que D-354 n'existe pas : l'éditeur l'alerte.

        ⓘ Le réglage est sur la ligne du produit RACINE ; le lien peut être posé dans un
        groupe sans produit. On lit donc la ligne du produit parent s'il pose la question,
        sinon toute ligne qui la déclare vendue à part.
        """
        self.ensure_one()
        attribute = self.swap_attribute_id
        if not attribute:
            return False
        Line = self.env["product.template.attribute.line"].sudo()
        tmpl = self.parent_id.product_tmpl_id
        own = tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id == attribute)[:1] \
            if tmpl else Line
        if own:
            return bool(own.sale_separately)
        return bool(Line.search_count([("attribute_id", "=", attribute.id),
                                       ("sale_separately", "=", True)], limit=1))

    @api.model
    def can_edit_conditions(self):
        """Oui : le pont sait ouvrir le dialogue des conditions (D-364).

        ⓘ C'est ce qui fait apparaître l'icône de condition dans l'éditeur 3D. Sans ce
        module, `product_editor` répond `False` et l'icône n'existe pas.
        """
        return True
