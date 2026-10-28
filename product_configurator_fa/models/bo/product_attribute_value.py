"""Ce que déclare `product.attribute.value` (BO, D-541)."""
from odoo import fields, models


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    default_extra_price_sqm = fields.Float(
        string="Default Extra Price per m²",
        digits="Product Price",
        help="Catalogue rate, copied onto each product that uses this value",
    )

    # Exposé pour les écrans de la VALEUR : le mode se déclare sur l'attribut,
    # mais c'est la valeur qu'on ouvre, et un champ ne peut pas se cacher sur
    # une information que son enregistrement ne porte pas.
    price_mode = fields.Selection(
        related="attribute_id.price_mode", string="Extra Price Mode", readonly=True
    )

    configurator_generated = fields.Boolean(
        string="Created by the Configurator",
        help="Set on values the configurator created from a free entry. "
        "Only these are candidates for the automatic cleanup.",
    )

    active = fields.Boolean(
        default=True,
        help="By unchecking the active field you can "
        "disable a attribute value without deleting it",
    )

    # ⚠️ Le type de l'attribut, LISIBLE DEPUIS LA VALEUR. Une vue ne sait pas
    # suivre `attribute_id.value_type` : elle n'évalue que des champs qu'elle
    # porte. Sans ce miroir, le formulaire d'une valeur ne peut pas masquer ce qui
    # ne le concerne pas — et il montrait le produit à TOUT LE MONDE, y compris aux
    # attributs de type « valeur ». Précédent du core, à la ligne près :
    # `display_type = fields.Selection(related='attribute_id.display_type')`.
    value_type = fields.Selection(
        related="attribute_id.value_type", string="Value Type", readonly=True
    )

    # ─ CE QUE LA VALEUR DÉSIGNE, quand ce n'est pas elle-même (D-196) ───────
    #
    # ⚠️ Ce champ EXISTAIT et n'était sur AUCUN écran. Il est pourtant lu à
    # l'exécution — `get_attribute_value_extra_prices` filtre sur
    # `("product_id", "!=", False)` pour prendre le prix du produit pointé plutôt
    # qu'un supplément saisi. Fonctionnalité complète et inatteignable, même
    # famille que le taux au m² (D-162). La colonne le rend enfin saisissable,
    # gouvernée par `value_type` comme les pastilles le sont par `display_type`.
    # ⓘ `product_id` a MIGRÉ vers `product_attribute_advanced` : c'est le premier
    # maillon de la permutation (D-164), et il vivait ici — donc hors d'atteinte de
    # l'éditeur, qui ne peut pas dépendre de ce module (D-075). Son prix, lui, reste
    # une affaire de configurateur et se lit sur le produit désigné.
    # ⚠️ REDEVENU UN `Image`, et ce n'est pas cosmétique. Le fork le redéfinissait
    # en `Binary` : sondé au runtime, il n'avait plus ni `max_width` ni contrôle
    # de résolution — une photo de plusieurs méga-octets partait telle quelle dans
    # une liste qui l'affiche en vignette, et un PDF déposé là passait sans un mot.
    #
    # ⓘ 256 px et non les 70 du core : la vignette du core suffit à sa liste, mais
    # le fork affiche cette image en `oe_avatar` sur sa propre fiche de valeur, où
    # 70 px remonteraient flous. C'est aussi la borne de la miniature des matières
    # (`preview_image`), ce qui garde une seule échelle dans le module.
    #
    # ⚠️ `Image` redimensionne à l'ÉCRITURE : les images déjà stockées gardent leur
    # taille jusqu'à un nouvel envoi. Mesuré avant d'écrire — une seule image en
    # base sur `fabk18`, 1,7 ko. Rien à reprendre.
    image = fields.Image(
        string="Image",
        max_width=256,
        max_height=256,
        help="Thumbnail shown when the attribute is displayed as colour swatches "
             "and no HTML colour is set.",
    )

    # ─ LE PRIX D'UNE VALEUR-PRODUIT SE LIT, IL NE SE SAISIT PAS — D-199 ─────
    #
    # ⚠️ Un montant modifiable serait trompeur : un seul produit de la liste corrigé
    # fausse les prix (D-199). MESURÉ sur la base de démo : le prix d'une
    # configuration tombait de 35 748 à 25 000, parce
    # qu'aucune valeur existante ne stocke de montant — toutes s'appuient sur le
    # prix du produit, et `test_04_compute_cfg_price` énonce cette règle ligne à
    # ligne. Un prix mi-saisi mi-hérité au sein d'une même liste, c'est en outre
    # deux sources pour un seul nombre : le lecteur ne peut plus savoir laquelle.
    #
    # ⓘ CE N'EST PAS EXACTEMENT LE MONTANT FACTURÉ, et il faut le savoir : la
    # facture applique le prix CONTEXTUEL, qui dépend de la liste de prix du
    # client. Dans un écran de CATALOGUE, afficher un prix qui change avec le
    # lecteur serait pire — d'où le prix de vente de base. Un écart ne peut venir
    # que d'une liste de prix, et il vient d'elle, pas d'ici.
    product_price = fields.Float(
        related="product_id.list_price",
        string="Product Price",
        readonly=True,
        help="Sale price of the product this value stands for. This is what is "
             "charged for this value — it cannot be overridden here.",
    )

    # Sans devise, `widget="monetary"` n'a rien à afficher.
    currency_id = fields.Many2one(related="product_id.currency_id", readonly=True)
