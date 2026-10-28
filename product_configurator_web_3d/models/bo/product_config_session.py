"""Ce que déclare `product.config.session` (BO, D-541)."""
from odoo import fields, models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    # ⚠️ `copy=False` : dupliquer une configuration ne duplique pas qui la tenait.
    hand_holder = fields.Char(
        string="Hand holder", copy=False,
        help="Opaque id of the page currently driving this configuration.",
    )

    hand_label = fields.Char(string="Hand label", copy=False)

    hand_since = fields.Datetime(string="Hand taken at", copy=False)

    # ── LES RÉPONSES PAR PLACEMENT — D-332 ──────────────────────────────────
    #
    # `value_ids` porte les réponses de la RACINE. Un enfant posé par un lien a ses propres
    # questions ; celles que l'auteur n'a pas fixées sur le lien se répondent ICI, par lien :
    # `{"<id de lien>": {"<id d'attribut>": <id de valeur>}}`. ⚠️ Les clés d'un `Json` sont
    # des CHAÎNES ([[L-219]]) : tout lecteur les convertit, jamais ne les compare brutes.
    #
    # ⓘ Une OCCURRENCE de répétition partage les réponses de son lien source — répondre
    # par copie est le cas de D-175, plus tard.
    child_values = fields.Json(
        string="Answers per placement", default=lambda self: {},
        help="Answers of the client to the questions of a placed part, per link.",
    )

    # La VARIANTE de chaque placement répondu, née à la confirmation — `{"<lien>": id}`.
    # ⚠️ Sans effet commercial tant que 7-9/7-10 ne sont pas faites : retenue, pas commandée.
    child_variants = fields.Json(
        string="Variants per placement", default=lambda self: {},
        help="Variant derived at confirmation for each answered placement.",
    )

    # Les SAISIES LIBRES par placement — `{"<lien>": {"<attribut>": "<saisie rangée>"}}`
    # (D-353). ⚠️ **Un champ À PART, pas dans `child_values`** : tous les lecteurs de
    # celui-ci attendent un IDENTIFIANT de valeur (`int(value_id)`), et une chaîne y
    # glissée les ferait tomber — ou pire, lire « 1500 » comme la valeur n° 1500.
    child_custom_values = fields.Json(
        string="Typed answers per placement", default=lambda self: {},
        help="Free answers typed by the client for a placed part, per link. They "
             "become attribute values only when the configuration is confirmed.",
    )

    variant_created = fields.Boolean(
        string="Variant created by this configuration", readonly=True, copy=False,
        help="The confirmation of this configuration CREATED its variant — it did not find "
             "an existing one. Only such a variant receives the picture taken by the "
             "customer's browser.",
    )
