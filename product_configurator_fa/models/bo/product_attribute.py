"""Ce que déclare `product.attribute` (BO, D-541)."""
from odoo import fields, models


class ProductAttribute(models.Model):
    _inherit = "product.attribute"
    _order = "sequence"

    # ─ CE QU'UNE VALEUR DÉSIGNE ──────────────────────────────────────────────
    #
    # ⚠️ TROIS notions, pas une liste de « types » qui mêlerait deux axes : liste, texte
    # et nombre ne sont pas des types, la saisie libre vaut pour les trois. Ce qui
    # distingue réellement les attributs :
    #
    #   · le TYPE, ici          — ce que la valeur DÉSIGNE ;
    #   · le FORMAT             — comment elle se LIT (`custom_type`, plus bas) ;
    #   · l'AJOUT par le client — un drapeau (`val_custom`).
    #
    # Les trois sont indépendants : une épaisseur est de type « valeur », de
    # format « entier », et peut être ouverte ou non à l'ajout.
    #
    # ⓘ « matière » n'est PAS ici : elle pointe une fiche de `product_editor`, et
    # c'est le module pont qui l'ajoute par `selection_add`. Pas pour une raison
    # de licence — D-075 autorise expressément le configurateur AGPL-3 à dépendre
    # de l'éditeur LGPL-3 — mais de MODULARITÉ : un configurateur sans éditeur 3D
    # doit continuer de fonctionner.
    # ─ LA LISTE PROPOSÉE PAR UN FILTRE — C2, D-207 ──────────────────────────
    #
    # D-207 : **QI** un filtre sur des PRODUITS uniquement,
    # **QJ** la valeur choisie est matérialisée, **QK** la liste dynamique n'existe
    # donc que pour les attributs de type produit. Les trois se referment l'une
    # l'autre : le filtre ne sert qu'à **proposer**, et ce qui est retenu devient
    # une valeur ordinaire — prix, archivage, historique continuent de marcher.
    #
    # ⚠️ **POURQUOI UNE CHAÎNE ICI, ALORS QUE D-080 REFUSE LE TEXTE.** D-080 porte
    # sur une CONDITION du configurateur — `(attribut, opérateur, valeurs)` —, et
    # sa raison est nommée : *« renommer une valeur, ou la traduire, ne casse
    # rien »*. Ce champ-ci n'est pas une condition : c'est un filtre sur un
    # **modèle réel**, `product.product`, dont les critères sont des champs Odoo
    # et dont les enregistrements cités le sont **par identifiant**. Renommer un
    # produit ne le casse pas davantage. Et c'est le mécanisme natif : `ir.filters`
    # et `ir.actions.act_window.domain` stockent ainsi.
    #
    # ⚠️ **Ce que ça coûte quand même** : un champ supprimé rendrait le filtre
    # invalide, et on ne le saurait qu'à la configuration — devant le client. D'où
    # la garde ci-dessous, qui l'évalue à l'enregistrement.
    # ─ LISTE FIXE OU LISTE DYNAMIQUE — le mode, D-218 ───────────────────────
    #
    # ⓘ Une coche « Dynamic values », offerte seulement quand la valeur désigne un
    # produit, et qui commande l'apparition du filtre.
    #
    # ⚠️ **CE N'EST PAS UN INTERRUPTEUR D'AFFICHAGE.** Deux régimes existent, et ce
    # champ dit lequel : soit on **tient** la liste, soit un **filtre la propose** et la
    # liste n'est plus qu'une trace de ce qui a été choisi (QJ).
    #
    # ⓘ Réservé au type « produit » (QK) : l'égalité d'une condition se vérifie sur
    # des produits, et un filtre ne sait proposer que cela.
    dynamic_values = fields.Boolean(
        string="Dynamic values",
        help="The values are proposed by a filter on products instead of being "
             "listed by hand. What the customer picks becomes an ordinary value.",
    )

    product_filter_domain = fields.Char(
        string="Product Filter",
        default="[]",
        help="Products proposed for this attribute. The filter only PROPOSES: "
             "what the customer picks becomes an ordinary attribute value.",
    )

    # ─ CE QUE LE FILTRE DONNE, AVANT DE S'EN SERVIR — C2, D-208 ─────────────
    #
    # ⓘ Le nombre de produits que le filtre donne, et leur liste dans un dialogue.
    #
    # ⚠️ Un domaine est une PROMESSE tant qu'on ne l'a pas appliqué. Écrit sans
    # retour, il se vérifie au pire moment — devant le client, quand la liste
    # proposée est vide ou compte trois cents lignes. Le compte le dit tout de
    # suite ; le dialogue montre lesquels.
    product_filter_count = fields.Integer(
        string="Products found",
        compute="_compute_product_filter_count",
    )

    # ⓘ `value_type`, `custom_type` et `NUMERIC_TYPES` vivent dans
    # `product_attribute_advanced`, avec leurs gardes, tels qu'ils étaient ici :
    # l'éditeur 3D en a besoin et ne peut pas dépendre d'un module AGPL-3 (D-075).
    # ⓘ `NUMERIC_TYPES` n'est pas d'origine OCA : il remplace un `("integer", "float")`
    # écrit en clair à trois endroits (D-195).
    #
    # ⓘ Les constantes de classe suivent l'héritage, Odoo ne construisant qu'UNE classe
    # par modèle : `self.NUMERIC_TYPES` répondrait toujours ici. Plus personne ne le lit
    # pourtant — `_is_numeric_custom` s'adosse désormais à `is_numeric()`, pour que la
    # règle ne soit écrite qu'une fois. Les 47 points d'appel de `custom_type`, eux,
    # n'ont rien vu passer.
    #
    # ⚠️ Ce qui RESTE ici est ce qui relève du configurateur seul : le régime des valeurs
    # (`dynamic_values`, `product_filter_domain`) et la purge de désignation, qui parlent
    # de la façon dont une liste se remplit — pas de ce qu'un attribut est.
    active = fields.Boolean(
        default=True,
        help="By unchecking the active field you can "
        "disable a attribute without deleting it",
    )

    # TODO: Exclude self from result-set of dependency
    val_custom = fields.Boolean(
        # ⚠️ « Valeur personnalisée » décrivait mal ce que ce drapeau DÉCLENCHE.
        # Une saisie libre ne reste pas éphémère : elle crée une vraie
        # `product.attribute.value`, marquée `configurator_generated`, avec une
        # unicité `(attribut, nom)` garantie en base (D-081).
        string="Default: customer may add a value",
        help="Default applied to a NEW product line. A value typed by the "
             "customer becomes a real attribute value, kept and reusable — not "
             "a throwaway entry.",
    )

    description = fields.Text(translate=True)

    search_ok = fields.Boolean(
        string="Searchable",
        help="When checking for variants with "
        "the same configuration, do we "
        "include this field in the search?",
    )

    # ─ LES QUATRE SEMENCES ──────────────────────────────────────────────────
    #
    # ⚠️ `required`, `multi`, `val_custom` et `price_mode` existent AUSSI sur la
    # ligne d'attribut d'un produit, et c'est la LIGNE que tout le monde lit — le
    # wizard (`line.multi or not line.required`), la session, les grilles de prix
    # (`ptav.attribute_line_id.price_mode`). Ceux-ci ne sont donc jamais consultés
    # à l'exécution : `onchange_attribute` les recopie sur la ligne à sa création,
    # et c'est tout.
    #
    # ⓘ Mesuré sur `fabk18` : 10 attributs sur 10 portent `required`, mais 2 lignes
    # sur 12 seulement — les autres sont nées sans que l'onchange joue. Ces champs ne
    # décident de rien.
    #
    # ⓘ Gardés pour le confort : « Couleur » obligatoire par nature évite de la cocher
    # produit par produit. ⚠️ Leur libellé commence par « Default: » — sans lui, on les
    # prend pour un réglage actif.
    required = fields.Boolean(
        default=True,
        string="Default: required",
        help="Default applied to a NEW product line. It decides nothing by "
             "itself: what is read at configuration time is the line's own "
             "setting, on the product.",
    )

    multi = fields.Boolean(
        string="Default: multiple values",
        help="Default applied to a NEW product line — see 'Default: required'.",
    )

    # ⓘ `uom_id` a MIGRÉ vers `product_attribute_advanced` : le module partagé le
    # porte pour les deux, et le catalogue d'unités d'Odoo apporte ses conversions —
    # huit unités de longueur, le pouce compris. Le définir ici en plus en ferait
    # deux définitions pour un seul champ.
    image = fields.Binary()

    price_mode = fields.Selection(
        selection=[("fixed", "Fixed amount"), ("per_sqm", "Per square meter")],
        default="fixed",
        required=True,
        string="Default: extra price mode",
        help="Default mode for the extra price of this attribute's values. "
        "Set on each product line, which is what actually applies.",
    )

    # ─ GRISER OU MASQUER — D-168, écrit par D-368 ───────────────────────────
    #
    # ⚠️ **PAS UNE SEMENCE**, contrairement aux quatre ci-dessus. Une semence n'est
    # lue qu'à l'onchange de la ligne, et `create()` l'oublie (2 lignes sur 12
    # portent `required` dans fabk18). Ici la LIGNE HÉRITE tant qu'elle est vide :
    # changer l'attribut change tous les produits qui ne l'ont pas surchargé. C'est
    # la règle de D-168 — « Couleur masque ses indisponibles partout, sauf sur le
    # produit qui préfère les griser ». Un seul lecteur : `_unavailable_display()`
    # de la ligne.
    unavailable_display = fields.Selection(
        selection=[("grey", "Greyed out"), ("hide", "Hidden")],
        default="grey",
        required=True,
        string="Unavailable values",
        help="What the configurator does with a value that the current choices rule "
        "out. Greyed out: it stays visible, and a tap says why. Hidden: it is not "
        "shown at all. A product line can override this setting.",
    )
