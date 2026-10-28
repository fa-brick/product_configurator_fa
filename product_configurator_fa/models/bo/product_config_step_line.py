"""Ce que déclare `product.config.step.line` (BO, D-541)."""
from odoo import fields, models


class ProductConfigStepLine(models.Model):
    _name = "product.config.step.line"
    _description = "Product Config Step Lines"
    _order = "sequence, config_step_id, id"

    # ⓘ « Une étape ne peut pas être déclarée deux fois sur le même produit » —
    # l'invariant compte plus que jamais, puisque deux lignes pour la même étape
    # se disputeraient les mêmes attributs et recevraient le même rang. Mais il
    # est DÉJÀ tenu, par `_check_config_step` plus bas.
    #
    # ⚠️ J'y avais ajouté une contrainte SQL. Elle était redondante, et nuisible :
    # posée en base, elle se levait AVANT la contrainte Python et remplaçait son
    # message par une violation d'index — les tests qui éprouvaient la règle
    # existante tombaient en erreur au lieu de passer ([[L-161]]).
    name = fields.Char(related="config_step_id.name")

    config_step_id = fields.Many2one(
        comodel_name="product.config.step",
        string="Configuration Step",
        required=True,
    )

    # ⚠️ **CE CHAMP EST DÉDUIT, PAS SAISI** — B1, D-202 : l'étape est un séparateur (ce
    # qui suit lui appartient jusqu'au suivant), l'appartenance se lit dans l'ORDRE.
    #
    # ⓘ Il garde son NOM et son sens : l'assistant, le configurateur et la page
    # publique continuent de lire `cfg_step.attribute_line_ids` sans changer d'une
    # ligne. Seule la source change.
    attribute_line_ids = fields.Many2many(
        comodel_name="product.template.attribute.line",
        string="Attribute Lines",
        compute="_compute_attribute_line_ids",
    )

    required = fields.Boolean(
        compute="_compute_required",
        # ⓘ Une étape est obligatoire si elle contient un attribut obligatoire (D-202) :
        # la contrainte est DÉRIVÉE, jamais déclarée.
        #
        # ⚠️ Et c'est un effet à distance : avec le séparateur, glisser une ligne
        # peut rendre une étape obligatoire, ou cesser de l'être. D'où ce champ —
        # une étape obligatoire doit se signaler d'elle-même dans la liste.
        help="Derived: this step is required because it carries at least one "
             "required attribute. Moving a line in or out changes it.",
    )

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product Template",
        ondelete="cascade",
        required=True,
    )

    # ⚠️ L'ORDRE DES ÉTAPES SUIT CELUI DES LIGNES, il ne se règle plus à part.
    # Deux poignées de tri indépendantes — une par liste — auraient produit des
    # numéros incomparables entre eux, et l'appartenance par position n'aurait
    # plus rien voulu dire. C'est la ligne qui OUVRE l'étape qui lui donne son rang.
    #
    # ⓘ Stocké parce que `_order` s'en sert : un calcul non stocké ne se trie pas
    # en SQL. Une étape que rien n'ouvre encore se range en dernier.
    sequence = fields.Integer(
        compute="_compute_sequence", store=True, default=10, readonly=True
    )

    visibility_domain_id = fields.Many2one(
        comodel_name="product.config.domain",
        string="Visibility Condition",
        ondelete="restrict",
        help="This step is shown only when the condition matches. "
        "Empty means always shown.",
    )
