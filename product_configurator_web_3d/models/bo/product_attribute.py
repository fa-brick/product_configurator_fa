"""Ce que déclare `product.attribute` (BO, D-541)."""
from odoo import fields, models


class ProductAttribute(models.Model):
    """Le type « matière » — l'attribut dont les valeurs désignent une FICHE.

    ⚠️ Ne pas le poser dans le cœur du configurateur : il pointe
    `product.model3d.material`, un modèle de `product_editor`, et un configurateur sans
    éditeur 3D doit continuer de fonctionner.
    ⓘ D-075 n'interdit PAS au configurateur AGPL-3 de dépendre de l'éditeur LGPL-3 : la
    raison est la MODULARITÉ, pas la licence.

    ─ Pourquoi une fiche et non une couleur ──────────────────────────────────

    ⚠️ Un code couleur ne montre ni le fil du bois ni le brossé du métal ; seule une fiche
    porte une `preview_image` (D-196).
    ⓘ Une matière dépend de la pièce (D-166) : « RAL 7016 » n'est pas la même fiche sur une
    poignée d'alu et sur un panneau d'acier.

    ⚠️ Le cas de D-166 ne disparaît pas — il se DÉPLACE. Une fiche « alu satiné »
    ne s'applique pas à un panneau d'acier, et la réponse n'est plus une table de
    correspondance mais **une question par famille de support** : la zone désigne
    déjà la sienne (`driver_attribute_id`), et une porte peut demander sa teinte
    intérieure et sa teinte extérieure à la fois.

    C'est alors, exactement, le patron de la face support : *« the attribute brings
    the products which may be laid here […] the support keeps NO list of its own »*.
    """
    _inherit = "product.attribute"

    # ⚠️ Ne pas ajouter « Matière » à `value_type` ici : l'ÉDITEUR la lit, et ne peut pas
    # dépendre de ce pont AGPL-3 (D-075). Elle vit dans `product_attribute_advanced`.
    #
    # ⓘ Ici vit le lien réel : la valeur qui pointe une fiche matière. Une
    # valeur de sélection ne nomme aucun modèle et n'entraîne aucune dépendance ; un
    # `Many2one` vers `product.model3d.material`, si.
    # ── LES FORMES D'AFFICHAGE SONT À CE MODULE (D-258) ──
    #
    # ⓘ La CARTE : un carré à coins arrondis portant la vignette, le libellé dessous.
    # ⓘ La GRANDE PASTILLE : un disque illustré de la matière ou de la teinte, son nom
    # dessous — 32 px ne montrent pas un bois.
    # ⚠️ Les formes à venir s'ajoutent ICI : `product_attribute_advanced` ne porte aucun
    # widget (D-258).
    # ⚠️ Ajoutées au champ du CŒUR : un second réglage « comment cette question
    # s'affiche » finirait par contredire le premier.
    # ⚠️ `website_sale.variants` n'a pas de `t-else` : sans `variants_card_fallback`, une
    # forme d'ici disparaît de la boutique, sans erreur (D-258).
    # ⚠️ Le dialogue de vente VALIDE `display_type` contre une liste fermée : sans
    # `sale_card_tolerance.js`, il tombe sur une forme d'ici (D-258).
    display_type = fields.Selection(
        selection_add=[("card", "Card"), ("swatch", "Large swatch")],
        ondelete={"card": "set default", "swatch": "set default"},
    )

    # ⓘ LA MARQUE DU CHOIX d'une grande pastille : l'anneau OU la coche, jamais les deux.
    # ⓘ Sur l'ATTRIBUT : la coche pour des bois, l'anneau pour une texture dont elle
    # cacherait le détail.
    swatch_mark = fields.Selection(
        selection=[("check", "Checkmark"), ("ring", "Ring")],
        default="check",
        required=True,
        string="Selection mark",
        help="How a large swatch shows that it is chosen: a checkmark in its centre, or a "
        "ring around it. The name below turns bold in both cases.",
    )

    # ⓘ LA TAILLE d'une carte ou d'une grande pastille ; le nombre par ligne en découle,
    # selon la place (D-382).
    # ⚠️ `medium` par défaut : c'est l'affichage d'avant ce champ, un attribut existant ne
    # bouge pas d'un pixel (D-382).
    answer_size = fields.Selection(
        selection=[("small", "Small"), ("medium", "Medium"), ("large", "Large")],
        default="medium",
        required=True,
        string="Answer size",
        help="Size of the cards or large swatches on the configurator page. How many fit "
        "on a row follows from the space available.",
    )

    # ⓘ **LA DISPOSITION des réponses** — D-382. `inline` est l'affichage d'avant : toutes les
    # réponses, dans la forme de la question. `scroll` et `line` ne valent que pour les
    # formes à image ; `summary` aussi pour les boutons et la liste.
    # ⚠️ **Pas de contrainte** sur le couple forme / disposition : elle interdirait de
    # changer la forme d'un attribut déjà réglé. Une combinaison sans effet retombe sur
    # `inline` au moment de servir (`_web_answer_layout`).
    answer_layout = fields.Selection(
        selection=[
            ("inline", "Full list"),
            ("scroll", "Horizontal scroll"),
            ("line", "One row + See all"),
            ("summary", "Summary line"),
        ],
        default="inline",
        required=True,
        string="Answer layout",
        help="How the answers are laid out on the configurator page. Horizontal scroll and "
        "One row only apply to cards and large swatches; Summary line also applies to "
        "radio, pills and select. Any other combination shows the full list.",
    )
