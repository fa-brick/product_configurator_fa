"""Ce qu'exécute `product.configurator.condition` (BLL, D-541)."""
from odoo import _, models
from odoo.exceptions import UserError


# Les deux préfixes sont identiques de part et d'autre ; on le VÉRIFIE plutôt que de le
# supposer (cf. `test_placement_condition.py`).
ATTRIBUTE_PREFIX = "__attribute_"


#: Opérateurs discrets que les deux grammaires partagent.
DISCRETE_OPS = ("in", "not in")


#: Comparaisons à un NOMBRE, pour l'éditeur comme pour le configurateur (D-267).
#: ⚠️ Les mêmes que `VISIBILITY_OPS_NUMERIC` (`visibility.js` de l'éditeur) : aucun test
#: ne tient l'égalité — un opérateur ajouté d'un seul côté serait lu par l'un, refusé par l'autre.
NUMERIC_OPS = ("=", "!=", ">", ">=", "<", "<=")


def _leaf_of(clause):
    """Une clause du moteur → une feuille d'éditeur de domaine."""
    if clause.get("op") in DISCRETE_OPS:
        return (clause["attr"], clause["op"], list(clause.get("values") or []))
    return (clause["attr"], clause["op"], clause.get("value"))


def clauses_to_domain(presence):
    """Les clauses d'un emplacement → le domaine préfixé que l'éditeur sait montrer.

    ⚠️ **LA GRAMMAIRE EST CELLE DE LA BARRE DE RECHERCHE** : ET entre les éléments, OU à
    l'intérieur d'un groupe (D-267 ; D-203 côté configurateur).
    C'est la MÊME des deux côtés, à dessein — un utilisateur qui passe de l'un à l'autre
    ne doit pas avoir à changer de façon de penser.

    ⓘ La forme préfixée d'un OU à trois feuilles est `["|", A, "|", B, C]` : le marqueur
    précède la feuille qui le porte, et la DERNIÈRE n'en émet jamais. C'est la convention
    d'Odoo, et celle que `to_odoo_domain` suit déjà pour les conditions du configurateur.
    """
    domain = []
    for element in (presence or {}).get("all") or []:
        groupe = element.get("any") if isinstance(element, dict) else None
        feuilles = [_leaf_of(c) for c in (groupe or [element])]
        domain.extend(["|"] * (len(feuilles) - 1))
        domain.extend(feuilles)
    return domain


def _clause_of(leaf, numeric_attributes=()):
    """Une feuille d'éditeur → une clause du moteur. Refuse ce qu'il ne saurait pas lire.

    ⚠️ **`=` VEUT DIRE DEUX CHOSES, et c'est la QUESTION qui tranche** : sur une question
    à valeurs, le sélecteur écrit `('champ', '=', id)` pour dire « parmi » ; sur une
    question numérique, `=` compare à un nombre. Les confondre stockerait un identifiant
    de valeur comme un nombre — une règle silencieusement fausse. C'est exactement la
    distinction que le configurateur fait de son côté.
    """
    name, op, value = leaf[0], leaf[1], leaf[2]
    if not str(name).startswith(ATTRIBUTE_PREFIX):
        raise UserError(_(
            "A placement condition tests the questions of the product, and nothing "
            "else — “%s” is not one of them.", name))
    # ⚠️ **LE SÉLECTEUR ÉCRIT `=`, LE MOTEUR LIT `in`** — et c'est le défaut du widget
    # pour un `many2one` : désigner une question produit `('__attribute_25', '=', 7)`.
    # Refuser sec rendrait le dialogue hostile (on n'a rien fait de faux) ; `=` et `!=`
    # disent exactement `in` et `not in` sur une valeur unique. C'est la traduction que
    # le configurateur fait déjà pour ses propres lignes — la même, au même endroit.
    if str(name) in numeric_attributes:
        if op not in NUMERIC_OPS:
            raise UserError(_(
                "“%s” is a numeric question: compare it to a number.", name))
        try:
            return {"attr": str(name), "op": op, "value": float(value)}
        except (TypeError, ValueError):
            raise UserError(_(
                "“%s” compares to a number: type a number.", name)) from None
    if op in ("=", "!="):
        if not isinstance(value, (list, tuple)):
            value = [value] if value else []
        value = [v for v in value if v]
        op = "in" if op == "=" else "not in"
    if op in DISCRETE_OPS:
        return {"attr": str(name), "op": op, "values": [int(v) for v in (value or [])]}
    raise UserError(_(
        "Operator “%s” cannot be stored on a placement: pick values, or compare a "
        "numeric question to a number.", op))


def domain_to_clauses(domain, groups=None, numeric_attributes=()):
    """Le domaine saisi → les éléments du moteur (clauses et groupes en OU).

    ⚠️ **LA LECTURE DU ET/OU EST CELLE DU CONFIGURATEUR, EMPRUNTÉE TELLE QUELLE.**
    `_parse_condition_groups` refuse déjà `A OU (B ET C)` — que ni son stockage ni le
    nôtre ne savent garder — et le dit avec ses mots. En écrire une seconde ici aurait
    donné deux lectures d'une même grammaire, dont une aurait fini par accepter ce que
    l'autre refuse.
    """
    if groups is None:
        raise UserError(_("This condition cannot be read."))
    elements = []
    for groupe in groups:
        clauses = [_clause_of(feuille, numeric_attributes) for feuille in groupe]
        elements.append(clauses[0] if len(clauses) == 1 else {"any": clauses})
    return elements


def merge_clauses(elements):
    """La présence recomposée — ou « toujours » quand il ne reste rien.

    ⓘ Plus rien à recoudre depuis que le dialogue montre TOUT ce que le moteur sait lire,
    comparaisons numériques comprises : ce qu'on a sous les yeux est ce qui sera écrit, et
    une clause ne peut plus disparaître pour n'avoir pas été affichée.
    """
    if not elements:
        # Une condition vidée n'est plus une condition : l'emplacement redevient
        # « toujours présent », ce que le dialogue de règle sait dire et montrer.
        return {"mode": "always"}
    return {"mode": "condition", "all": list(elements)}


class ProductConfiguratorCondition(models.TransientModel):
    _inherit = "product.configurator.condition"

    def open_for_component(self, component, product_tmpl):
        assistant = self.create({
            "product_tmpl_id": product_tmpl.id,
            "component_id": component.id,
            "condition_domain": str(
                clauses_to_domain((component.visibility or {}).get("presence"))),
        })
        return assistant._open(
            _('Condition of "%s"', component.child_id.display_name))

    def _numeric_field_names(self):
        """Les champs qui désignent une question NUMÉRIQUE — `{__attribute_<id>}`.

        ⓘ C'est la seule chose qui distingue `= 7` (« la valeur 7 ») de `= 7` (« sept
        millimètres ») : l'opérateur ne le dit pas, la question si.
        """
        domaine = self.env["product.config.domain"]
        attributs = self.env["product.attribute"].search(
            [("id", "in", self.product_tmpl_id.attribute_line_ids.attribute_id.ids)])
        return {domaine._attribute_field_name(a) for a in attributs if a.is_numeric()}

    def _apply_condition(self, domain):
        if not self.component_id:
            return super()._apply_condition(domain)
        composant = self.component_id
        # ⓘ La lecture du ET/OU est EMPRUNTÉE au configurateur : mêmes règles, mêmes
        # refus, mêmes messages (D-267).
        groupes = self.env["product.config.domain"]._parse_condition_groups(domain)
        visibility = dict(composant.visibility or {})
        visibility["presence"] = merge_clauses(
            domain_to_clauses(domain, groupes, self._numeric_field_names()))
        composant.visibility = visibility
        return True
