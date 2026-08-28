from ast import literal_eval
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductAttributeBoundMixin(models.AbstractModel):
    """Les trois bornes d'un attribut numérique — mini, maxi, pas.

    Porté par DEUX modèles : la ligne d'attribut (les bornes par défaut) et la
    borne conditionnelle (celles qui s'appliquent quand un domaine est
    satisfait). Le mixin évite que les deux divergent — D-089.

    ⚠️ `has_min_val` / `has_max_val` ne sont pas du confort : un `fields.Float`
    d'Odoo ne peut PAS être nul (`convert_to_column` fait `float(value or 0.0)`,
    odoo/fields.py:1670). Sans le drapeau, une borne légitimement nulle serait
    indistinguable d'une absence de borne — le défaut d'OCA que D-089 nomme.
    Le `step`, lui, n'a pas besoin de drapeau : un pas de zéro n'a pas de sens,
    donc zéro veut dire « pas de pas », sans ambiguïté.
    """

    _name = "product.attribute.bound.mixin"
    _description = "Bounds of a Numeric Attribute (min / max / step)"

    has_min_val = fields.Boolean(
        string="Has Minimum",
        help="Check to enforce a minimum value. Needed to tell "
        "'no minimum' from 'a minimum of zero'.",
    )
    min_val = fields.Float(
        string="Minimum Value",
        digits=(16, 4),
        help="Minimum value allowed, enforced only when 'Has Minimum' is set",
    )
    has_max_val = fields.Boolean(
        string="Has Maximum",
        help="Check to enforce a maximum value. Needed to tell "
        "'no maximum' from 'a maximum of zero'.",
    )
    max_val = fields.Float(
        string="Maximum Value",
        digits=(16, 4),
        help="Maximum value allowed, enforced only when 'Has Maximum' is set",
    )
    step = fields.Float(
        string="Step",
        digits=(16, 4),
        help="Allowed increment between the minimum and the maximum. "
        "Zero means any value is allowed.",
    )

    @api.constrains("has_min_val", "min_val", "has_max_val", "max_val", "step")
    def _check_bounds_consistency(self):
        for record in self:
            if (
                record.has_min_val
                and record.has_max_val
                and record.max_val < record.min_val
            ):
                raise ValidationError(
                    self.env._("Maximum value must be greater than Minimum value")
                )
            if record.step < 0:
                raise ValidationError(self.env._("Step must not be negative"))

    def _as_bounds(self, cause=None):
        """Rend les bornes sous une forme neutre — `None` dit « pas de borne ».

        Le reste du code raisonne sur ce dictionnaire et jamais sur les champs :
        c'est ce qui empêche le `if minv and maxv` d'OCA de revenir, et c'est ce
        qui permet à une borne conditionnelle et à une borne par défaut d'être
        consommées par le même code.
        """
        self.ensure_one()
        return {
            "min_val": self.min_val if self.has_min_val else None,
            "max_val": self.max_val if self.has_max_val else None,
            "step": self.step or None,
            "cause": cause,
        }


class ProductAttributeBound(models.Model):
    """Une borne qui ne s'applique QUE si son domaine est satisfait — D-076.

    « Ligne de ressort arrière → largeur maxi 4 000 » s'écrit ici, et le domaine
    référence les valeurs par leur ENREGISTREMENT : renommer une valeur ne casse
    donc rien, par construction. C'est ce qui a rendu inutile le code technique
    que D-076 réclamait d'abord sur les valeurs.
    """

    _name = "product.attribute.bound"
    _inherit = ["product.attribute.bound.mixin"]
    _description = "Conditional Bound of a Product Attribute Line"
    _order = "sequence, id"

    attribute_line_id = fields.Many2one(
        comodel_name="product.template.attribute.line",
        string="Attribute Line",
        required=True,
        ondelete="cascade",
        index=True,
    )
    domain_id = fields.Many2one(
        comodel_name="product.config.domain",
        string="Condition",
        required=True,
        ondelete="restrict",
        help="Bounds below apply only to configurations matching this condition",
    )
    sequence = fields.Integer(
        default=10,
        help="First matching line wins, so order matters",
    )

    @api.depends("domain_id")
    def _compute_display_name(self):
        for bound in self:
            bound.display_name = bound.domain_id.name or self.env._("Bound")


class ProductAttribute(models.Model):
    _inherit = "product.attribute"
    _order = "sequence"

    def copy(self, default=None):
        """Add ' (Copy)' in name to prevent attribute
        having same name while copying"""
        if not default:
            default = {}
        new_attrs = self.env["product.attribute"]
        for attr in self:
            default.update({"name": attr.name + " (copy)"})
            new_attrs += super(ProductAttribute, attr).copy(default)
        return new_attrs

    @api.model
    def _get_nosearch_fields(self):
        """Return a list of custom field types that do not support searching"""
        return ["binary"]

    @api.onchange("custom_type")
    def onchange_custom_type(self):
        if self.custom_type in self._get_nosearch_fields():
            self.search_ok = False
        # ⚠️ Les bornes ne sont plus ici (D-089) : « Largeur » est partagée par
        # un portail et une porte de garage, une borne globale ne peut être
        # juste pour personne. Le nettoyage des bornes devenues sans objet se
        # fait donc sur la LIGNE, dans `onchange_attribute`.

    @api.onchange("val_custom")
    def onchange_val_custom_field(self):
        if not self.val_custom:
            self.custom_type = False

    # ─ CE QU'UNE VALEUR DÉSIGNE — A2, arbitré par Gerry le 2026-08-28 ────────
    #
    # ⚠️ TROIS notions, et non une. La première tentative en proposait cinq —
    # « liste, nombre, texte, produit, matière » — et mélangeait deux axes. Gerry
    # a tranché : *« pour moi liste et texte sont la même chose, et même nombre,
    # la saisie libre est possible »*. Ce qui distingue réellement les attributs :
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
    VALUE_TYPES = [
        ("value", "Value"),
        ("product", "Product"),
    ]

    value_type = fields.Selection(
        selection=VALUE_TYPES,
        string="Value type",
        default="value",
        required=True,
        help="What a value of this attribute DESIGNATES.\n\n"
             "- Value: nothing but itself — a label chosen from a list. How that "
             "label is read (text, number, date) is the FORMAT, and whether the "
             "customer may add one is a separate flag.\n"
             "- Product: the value designates a product, and its list may be "
             "proposed by a filter.\n\n"
             "It is the type that lets a screen know what to show: a product "
             "picker, a material thumbnail, or a plain label.",
    )

    # ⚠️ LE FORMAT ET L'UNITÉ N'ONT DE SENS QUE POUR LE TYPE « VALEUR ».
    #
    # Constat de Gerry (2026-08-28) : *« on peut choisir value type : product et
    # format integer, ça n'a pas de sens »*. Il a raison, et le défaut est de moi :
    # j'ai posé trois notions INDÉPENDANTES — type, format, ajout — ce qui est
    # juste, et j'en ai conclu qu'aucune ne contraignait les autres, ce qui est
    # faux. Un format dit comment LIRE un libellé ; quand la valeur désigne un
    # produit ou une fiche matière, il n'y a pas de libellé à lire, l'objet EST la
    # réponse. Idem pour l'unité, qui appartient alors au produit.
    #
    # DEUX BARRIÈRES, comme pour l'éditeur de conditions (D-080) : la vue masque
    # ces deux champs hors du type « valeur », et cette contrainte refuse la
    # combinaison quelle que soit l'interface — import, ORM, script.
    #
    # ⚠️ Et un `onchange` NETTOIE en basculant le type. Sans lui, un format saisi
    # avant la bascule resterait, invisible, et le refus tomberait sur un champ
    # que l'utilisateur ne voit plus : le pire des messages d'erreur.
    @api.constrains("value_type", "custom_type", "uom_id")
    def _check_format_only_for_plain_values(self):
        for attribute in self:
            if attribute.value_type == "value":
                continue
            if attribute.custom_type or attribute.uom_id:
                raise ValidationError(
                    self.env._(
                        "A format and a unit only make sense when a value designates "
                        "nothing but itself. Here a value designates a %s: the object "
                        "is the answer, there is no label to read.",
                        dict(self._fields["value_type"].selection).get(
                            attribute.value_type, attribute.value_type
                        ),
                    )
                )

    @api.onchange("value_type")
    def _onchange_value_type(self):
        if self.value_type != "value":
            self.custom_type = False
            self.uom_id = False

    CUSTOM_TYPES = [
        ("char", "Char"),
        ("integer", "Integer"),
        ("float", "Float"),
        ("text", "Textarea"),
        ("color", "Color"),
        ("binary", "Attachment"),
        ("date", "Date"),
        ("datetime", "DateTime"),
    ]

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
        # unicité `(attribut, nom)` garantie en base (D-081). Gerry l'a relu
        # ainsi le 2026-08-27 — « custom, qui est ajout par l'utilisateur
        # possible finalement » —, et c'est exactement ce que le code fait.
        string="Default: customer may add a value",
        help="Default applied to a NEW product line. A value typed by the "
             "customer becomes a real attribute value, kept and reusable — not "
             "a throwaway entry.",
    )
    custom_type = fields.Selection(
        selection=CUSTOM_TYPES,
        string="Field Type",
        help="The type of the custom field generated in the frontend",
    )
    description = fields.Text(translate=True)
    search_ok = fields.Boolean(
        string="Searchable",
        help="When checking for variants with "
        "the same configuration, do we "
        "include this field in the search?",
    )
    # ─ LES QUATRE SEMENCES — A4, arbitrage Gerry (2026-08-28) ───────────────
    #
    # ⚠️ `required`, `multi`, `val_custom` et `price_mode` existent AUSSI sur la
    # ligne d'attribut d'un produit, et c'est la LIGNE que tout le monde lit — le
    # wizard (`line.multi or not line.required`), la session, les grilles de prix
    # (`ptav.attribute_line_id.price_mode`). Ceux-ci ne sont donc jamais consultés
    # à l'exécution : `onchange_attribute` les recopie sur la ligne à sa création,
    # et c'est tout.
    #
    # Mesuré sur `fabk18` avant de trancher : 10 attributs sur 10 portent
    # `required`, mais 2 lignes sur 12 seulement — les autres ont été créées sans
    # que l'onchange joue. Elles ne sont pas obligatoires, et personne ne s'en est
    # plaint : la preuve que ces champs ne décident de rien.
    #
    # Gerry a choisi de les GARDER — la semence est un confort réel, déclarer
    # « Couleur » obligatoire par nature évite de la cocher produit par produit —
    # à condition que leur libellé cesse de faire croire à un réglage actif. D'où
    # le « Default: » qui ouvre chacun d'eux.
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
    uom_id = fields.Many2one(comodel_name="uom.uom", string="Unit of Measure")
    image = fields.Binary()
    price_mode = fields.Selection(
        selection=[("fixed", "Fixed amount"), ("per_sqm", "Per square meter")],
        default="fixed",
        required=True,
        string="Default: extra price mode",
        help="Default mode for the extra price of this attribute's values. "
        "Set on each product line, which is what actually applies.",
    )

    # TODO prevent the same attribute from being defined twice on the
    # attribute lines

    @api.constrains("custom_type", "search_ok")
    def check_searchable_field(self):
        for attribute in self:
            nosearch_fields = attribute._get_nosearch_fields()
            if attribute.custom_type in nosearch_fields and attribute.search_ok:
                raise ValidationError(
                    self.env._(
                        "Selected custom field type '%s' is not searchable",
                        attribute.custom_type,
                    )
                )

    def _is_numeric_custom(self):
        """Un attribut dont la valeur EST un nombre."""
        self.ensure_one()
        return self.custom_type in ("integer", "float")

    def canonical_custom_value(self, value):
        """La forme STOCKÉE d'une valeur numérique : le nombre, et rien d'autre.

        ⚠️ Sans elle, `2400`, `2400.0` et ` 2400 ` sont trois chaînes
        différentes — donc trois valeurs d'attribut différentes le jour où une
        dimension se range en valeur (D-081), pour une seule et même largeur.
        La mise en forme ne REFUSE jamais : ce qui n'est pas un nombre ressort
        tel quel, et c'est `validate_custom_val` qui tranche.
        """
        self.ensure_one()
        if not self._is_numeric_custom() or value in (None, False, ""):
            return value
        try:
            number = float(str(value).strip())
        except (TypeError, ValueError):
            return value
        if number.is_integer():
            return str(int(number))
        return f"{number:.6f}".rstrip("0").rstrip(".")

    def format_custom_value(self, value):
        """La forme AFFICHÉE : le nombre, puis son unité.

        La valeur reste le nombre — l'unité ne s'écrit nulle part en base, elle
        se rajoute à l'affichage. L'y stocker ferait d'un changement d'unité une
        migration de données, et d'une comparaison de largeurs une comparaison
        de chaînes.
        """
        self.ensure_one()
        text = self.canonical_custom_value(value)
        if text in (None, False, "") or not self.uom_id:
            return text
        return f"{text} {self.uom_id.name}"

    def _resolves_to_values(self):
        """Un nombre saisi sur cet attribut se RANGE-t-il en valeur d'attribut ?

        La question n'a pas besoin d'un champ neuf : `create_variant` la porte
        déjà. En `no_variant`, la valeur ne peut pas entrer dans l'identité
        d'une variante — la ranger ne servirait à rien. Partout ailleurs, elle
        le peut, et c'est tout l'objet de D-081 : le stock ne sait distinguer
        deux portes que par leurs valeurs d'attribut.
        """
        self.ensure_one()
        return self._is_numeric_custom() and self.create_variant != "no_variant"

    def resolve_numeric_value(self, number):
        """Rend LA valeur d'attribut qui porte ce nombre — en la créant au besoin.

        ⚠️ Le motif « je cherche, sinon je crée » est un *check-then-insert* :
        deux clients validant 3 200 au même instant passent tous deux le test,
        et le stock se coupe en deux. La contrainte d'unicité en base est ce qui
        tranche vraiment (`init`) ; ici, on rattrape sa violation plutôt que de
        prétendre l'éviter.

        Une valeur ARCHIVÉE est ressuscitée plutôt que dupliquée : le ménage
        archive (D-082), et une largeur qui revient est la même largeur.
        """
        self.ensure_one()
        name = self.canonical_custom_value(number)
        value_obj = self.env["product.attribute.value"]
        domain = [("attribute_id", "=", self.id), ("name", "=", name)]
        existing = value_obj.with_context(active_test=False).search(domain, limit=1)
        if existing:
            if not existing.active:
                existing.active = True
            return existing
        vals = {
            "attribute_id": self.id,
            "name": name,
            "configurator_generated": True,
        }
        try:
            with self.env.cr.savepoint():
                return value_obj.sudo().create(vals).with_env(self.env)
        except IntegrityError:
            # Quelqu'un d'autre a créé la même largeur entre-temps : c'est la
            # base qui l'a dit, et c'est la seule autorité qui pouvait le dire.
            return value_obj.with_context(active_test=False).search(domain, limit=1)

    def _configurator_value_ids(self):
        """Values accepted for attributes in `self`."""
        values = self.value_ids
        if any(self.mapped("val_custom")):
            values += self.env["product.config.session"].get_custom_value_id()
        return values


class ProductAttributeLine(models.Model):
    # ⚠️ Avec un `_inherit` en LISTE, `_name` cesse d'être déduit : sans cette
    # ligne, Odoo prend le nom de la CLASSE pour nom de modèle et refuse de
    # démarrer (`models.py:143`).
    _name = "product.template.attribute.line"
    _inherit = ["product.template.attribute.line", "product.attribute.bound.mixin"]
    _order = "product_tmpl_id, sequence, id"
    # TODO: Order by dependencies first and then sequence so dependent fields
    # do not come before master field

    @property
    def _prefixes(self):
        return self.env["product.configurator"]._prefixes

    @api.onchange("attribute_id")
    def onchange_attribute(self):
        """Set default value of required/multi/cutom from attribute"""
        self.value_ids = False
        self.required = self.attribute_id.required
        self.multi = self.attribute_id.multi
        self.custom = self.attribute_id.val_custom
        self.price_mode = self.attribute_id.price_mode
        # Des bornes sur un attribut qui n'est plus numérique ne s'appliqueraient
        # jamais : les laisser en place, c'est afficher une règle inerte.
        if self.attribute_id.custom_type not in ("integer", "float"):
            self.has_min_val = False
            self.min_val = 0
            self.has_max_val = False
            self.max_val = 0
            self.step = 0
            self.bound_ids = False
        # TODO: Remove all dependencies pointed towards the attribute being
        # changed

    @api.onchange("value_ids")
    def onchange_values(self):
        if self.default_val and self.default_val not in self.value_ids:
            self.default_val = None

    custom = fields.Boolean(help="Allow custom values for this attribute?")
    required = fields.Boolean(help="Is this attribute required?")
    required_condition = fields.Char(compute="_compute_attribute_condition", store=True)
    invisible_condition = fields.Char(
        compute="_compute_attribute_condition", store=True
    )
    readonly_condition = fields.Char(compute="_compute_attribute_condition", store=True)
    multi = fields.Boolean(
        help="Allow selection of multiple values for this attribute?",
    )
    default_val = fields.Many2one(comodel_name="product.attribute.value")

    sequence = fields.Integer(default=10)

    dimension_role = fields.Selection(
        selection=[
            ("axis_x", "Grid axis X (columns)"),
            ("axis_y", "Grid axis Y (rows)"),
        ],
        string="Dimension Role",
        help="What this dimension is FOR, as opposed to what it is called. "
        "The price grid is indexed by these two roles, and the surface used "
        "by per-square-meter extras is their product.",
    )
    price_mode = fields.Selection(
        selection=[("fixed", "Fixed amount"), ("per_sqm", "Per square meter")],
        default="fixed",
        required=True,
        string="Extra Price Mode",
        help="How the extra price of this attribute's values is read on this "
        "product: a flat amount, or a rate per square meter",
    )

    visibility_domain_id = fields.Many2one(
        comodel_name="product.config.domain",
        string="Visibility Condition",
        ondelete="restrict",
        help="This attribute is asked only when the condition matches. "
        "Empty means always asked.",
    )

    bound_ids = fields.One2many(
        comodel_name="product.attribute.bound",
        inverse_name="attribute_line_id",
        string="Conditional Bounds",
        copy=True,
        help="Bounds that replace the ones above when their condition matches. "
        "The first matching line wins.",
    )
    # Exposé pour les vues seulement : le type vit sur l'attribut, mais c'est la
    # ligne qu'on édite, et un champ absent de la vue ne peut pas la conditionner.
    attribute_custom_type = fields.Selection(
        related="attribute_id.custom_type", string="Field Type", readonly=True
    )

    def _is_visible(self, value_ids=None, custom_vals=None):
        """L'attribut est-il demandé pour cette configuration ? — D-086.

        ⚠️ C'est le niveau du MILIEU, celui qui n'existait pas. Aujourd'hui un
        attribut ne disparaît que par effet de bord — toutes ses valeurs
        écartées — et il en découle deux défauts : un attribut NUMÉRIQUE, qui
        n'a pas de valeurs, ne peut pas être masqué du tout ; et un masquage par
        effet de bord ne se LIT pas, donc l'utilisateur voit un attribut
        disparaître sans qu'aucune règle visible ne l'explique.
        """
        self.ensure_one()
        if not self.visibility_domain_id:
            return True
        session = self.env["product.config.session"]
        return session.validate_domains_against_sels(
            self.visibility_domain_id.compute_domain(),
            value_ids or [],
            custom_vals or {},
        )

    def _get_bounds(self, value_ids=None, custom_vals=None):
        """Rend les bornes applicables à cette ligne pour une configuration.

        La PREMIÈRE borne conditionnelle dont le domaine est satisfait gagne, et
        elle remplace les bornes par défaut ENTIÈREMENT — jamais champ par champ.
        Fusionner un maxi conditionnel avec un mini par défaut donnerait une règle
        que personne n'a écrite nulle part, et qui ne se lit dans aucun écran.
        Aucune ne correspond : les bornes portées par la ligne s'appliquent.

        ⚠️ Un domaine VIDE est satisfait — c'est la sémantique de
        `validate_domains_against_sels`, la même que pour les valeurs disponibles.
        """
        self.ensure_one()
        session = self.env["product.config.session"]
        for bound in self.bound_ids:
            domains = bound.domain_id.compute_domain()
            if session.validate_domains_against_sels(
                domains, value_ids or [], custom_vals or {}
            ):
                return bound._as_bounds(cause=bound.domain_id.name)
        return self._as_bounds()

    def _format_bound(self, value):
        """« 4000 mm » — une borne s'affiche comme la valeur qu'elle borne.

        Le formatage vit sur l'ATTRIBUT et pas ici : une borne, une saisie et
        une valeur rangée sont le même nombre vu à trois moments, et trois
        mises en forme finiraient par diverger.
        """
        self.ensure_one()
        return self.attribute_id.format_custom_value(value)

    @api.model
    def _bound_tolerance(self, *values):
        """Tolérance de comparaison — un flottant ne tombe jamais juste."""
        return max(abs(v) for v in (*values, 1.0)) * 1e-9

    def _suggest_val(self, val, bounds):
        """La valeur admissible la plus proche, ou `None` s'il n'en existe pas.

        C'est la moitié « en PROPOSANT » de D-077 : refuser sans montrer le seul
        chemin enferme l'utilisateur dans un ordre imposé qu'il doit deviner.
        """
        minv, maxv, step = bounds["min_val"], bounds["max_val"], bounds["step"]
        suggestion = val
        if minv is not None and suggestion < minv:
            suggestion = minv
        if maxv is not None and suggestion > maxv:
            suggestion = maxv
        if step:
            base = minv if minv is not None else 0.0
            suggestion = base + round((suggestion - base) / step) * step
            tol = self._bound_tolerance(suggestion, step)
            # Le pas peut faire sortir des bornes : on rentre, on ne sort jamais.
            if minv is not None and suggestion < minv - tol:
                suggestion += step
            if maxv is not None and suggestion > maxv + tol:
                suggestion -= step
        return None if self._bounds_error(suggestion, bounds) else suggestion

    def _bounds_error(self, val, bounds):
        """Rend le message d'erreur, ou `None` si la valeur passe.

        Rendre un message plutôt que lever laisse l'interface DEMANDER si une
        valeur passe — le dialogue de D-077 a besoin de le savoir avant que
        l'utilisateur ne valide, pas après.
        """
        self.ensure_one()
        minv, maxv, step = bounds["min_val"], bounds["max_val"], bounds["step"]
        name = self.attribute_id.name
        tol = self._bound_tolerance(val, minv or 0.0, maxv or 0.0, step or 0.0)
        message = None
        if minv is not None and val < minv - tol:
            message = self.env._(
                "Custom value %(val)s for '%(name)s' is below the minimum "
                "of %(min_val)s.",
                val=self._format_bound(val),
                name=name,
                min_val=self._format_bound(minv),
            )
        elif maxv is not None and val > maxv + tol:
            message = self.env._(
                "Custom value %(val)s for '%(name)s' is above the maximum "
                "of %(max_val)s.",
                val=self._format_bound(val),
                name=name,
                max_val=self._format_bound(maxv),
            )
        elif step:
            base = minv if minv is not None else 0.0
            offset = abs((val - base) % step)
            if offset > tol and abs(offset - step) > tol:
                message = self.env._(
                    "Custom value %(val)s for '%(name)s' must go by steps "
                    "of %(step)s from %(base)s.",
                    val=self._format_bound(val),
                    name=name,
                    step=self._format_bound(step),
                    base=self._format_bound(base),
                )
        if message is None:
            return None
        if bounds.get("cause"):
            message += " " + self.env._(
                "This limit comes from condition '%(cause)s'.",
                cause=bounds["cause"],
            )
        suggestion = self._suggest_val(val, bounds)
        if suggestion is not None:
            message += " " + self.env._(
                "Nearest allowed value: %(suggestion)s.",
                suggestion=self._format_bound(suggestion),
            )
        return message

    @api.constrains("dimension_role", "product_tmpl_id")
    def _check_dimension_role_unique(self):
        """Un rôle, un seul porteur par produit — sinon la grille ne sait plus
        quelle cote lire, et le choix se ferait par l'ordre des lignes."""
        for line in self.filtered("dimension_role"):
            twin = self.search(
                [
                    ("product_tmpl_id", "=", line.product_tmpl_id.id),
                    ("dimension_role", "=", line.dimension_role),
                    ("id", "!=", line.id),
                ],
                limit=1,
            )
            if twin:
                raise ValidationError(
                    self.env._(
                        "'%(attribute)s' already plays this role on %(product)s",
                        attribute=twin.attribute_id.display_name,
                        product=line.product_tmpl_id.display_name,
                    )
                )
            if not line.attribute_id._is_numeric_custom():
                raise ValidationError(
                    self.env._(
                        "Only a numeric attribute can carry a grid axis — "
                        "'%(attribute)s' is not one",
                        attribute=line.attribute_id.display_name,
                    )
                )

    def resolve_numeric_value(self, number):
        """Rend la valeur d'attribut de ce nombre, et l'ATTACHE à cette ligne.

        L'attachement n'est pas un extra : une valeur absente de la ligne n'a
        pas de `product.template.attribute.value`, et une variante ne peut
        porter que des ptav. Sans lui, la largeur serait rangée au catalogue
        global et n'entrerait dans l'identité d'aucune variante — le stock
        resterait aveugle, c'est-à-dire exactement le défaut que D-081 corrige.

        ⚠️ `sudo()` : celui qui configure n'a pas le droit d'écrire sur le
        produit, et il ne doit pas l'avoir. C'est le même geste que la création
        de la variante, elle aussi en `sudo()` chez OCA.
        """
        self.ensure_one()
        value = self.attribute_id.resolve_numeric_value(number)
        if value not in self.value_ids:
            self.sudo().write({"value_ids": [(4, value.id)]})
        return value

    def validate_custom_val(self, val, value_ids=None, custom_vals=None):
        """Refuse une saisie hors bornes — D-077, et sur la LIGNE, D-089.

        ⚠️ Le configurateur REFUSE là où le moteur borne (D-040 B) : il traite
        une saisie humaine, dont la valeur engage une commande.
        """
        self.ensure_one()
        if self.attribute_id.custom_type not in ("integer", "float"):
            return
        val = literal_eval(str(val))
        message = self._bounds_error(val, self._get_bounds(value_ids, custom_vals))
        if message:
            raise ValidationError(message)

    @api.depends(
        "required", "custom", "product_tmpl_id", "product_tmpl_id.config_step_line_ids"
    )
    def _compute_attribute_condition(self):
        for line in self:
            config_steps = line.product_tmpl_id.config_step_line_ids.filtered(
                lambda x, attr_line=line: attr_line in x.attribute_line_ids
            )
            depends = line.get_dependencies()
            line.required_condition = line.get_required_condition(config_steps, depends)
            line.readonly_condition = line.get_readonly_condition(config_steps, depends)
            line.invisible_condition = line.get_invisible_condition(config_steps)

    def get_required_condition(self, config_steps, dependencies):
        self.ensure_one()
        required_str = ""
        if self.required:
            if config_steps:
                if self.required:
                    cfg_step_ids = [str(id) for id in config_steps.ids]
                    required_str += f"state in {cfg_step_ids}"
                else:
                    required_str += "state in ['configure']"
            for depend_field, val_ids in dependencies.items():
                if not val_ids:
                    continue
                field_type = "many2many" if self.multi else "many2one"
                if self.required and not self.custom and field_type != "many2many":
                    if required_str:
                        required_str += " and "
                    required_str += f"{depend_field} in {str(list(val_ids))}"
        return required_str

    def get_invisible_condition(self, config_steps):
        self.ensure_one()
        if config_steps:
            cfg_step_ids = [str(id) for id in config_steps.ids]
            return f"state not in {cfg_step_ids}"
        else:
            return "state not in ['configure']"

    def get_readonly_condition(self, config_steps, dependencies):
        self.ensure_one()
        readonly_str = ""
        if config_steps:
            cfg_step_ids = [str(id) for id in config_steps.ids]
            readonly_str += f"state not in {cfg_step_ids}"
        else:
            readonly_str += "state not in ['configure']"
        for depend_field, val_ids in dependencies.items():
            if not val_ids:
                continue
            field_type = "many2many" if self.multi else "many2one"
            if field_type != "many2many":
                if readonly_str:
                    readonly_str += " and "
                readonly_str += f"{depend_field} not in {str(list(val_ids))}"
        return readonly_str

    def get_dependencies(self):
        self.ensure_one()
        field_prefix = self._prefixes.get("field_prefix")
        config_lines = self.product_tmpl_id.config_line_ids
        dependencies = config_lines.filtered(
            lambda cl, attr_line=self: cl.attribute_line_id == attr_line
        )
        attr_depends = {}
        if self.value_ids <= dependencies.mapped("value_ids"):
            domain_lines = dependencies.mapped("domain_id.domain_line_ids")
            for domain_line in domain_lines:
                attr_id = domain_line.attribute_id.id
                attr_field = field_prefix + str(attr_id)
                attr_lines = self.product_tmpl_id.attribute_line_ids
                # If the fields it depends on are not in the config step
                # allow to update attrs for all attribute.\ otherwise
                # required will not work with stepchange using statusbar.
                # if config_steps and wiz.state not in cfg_step_ids:
                #     continue
                if attr_field not in attr_depends:
                    attr_depends[attr_field] = set()
                if domain_line.condition == "in":
                    attr_depends[attr_field] |= set(domain_line.value_ids.ids)
                elif domain_line.condition == "not in":
                    val_ids = attr_lines.filtered(
                        lambda line, attr_id=self: line.attribute_id.id == attr_id
                    ).value_ids
                    val_ids = val_ids - domain_line.value_ids
                    attr_depends[attr_field] |= set(val_ids.ids)
        return attr_depends

    @api.constrains("value_ids", "default_val")
    def _check_default_values(self):
        """default value should not be outside of the
        values selected in attribute line"""
        for line in self.filtered(lambda line: line.default_val):
            if line.default_val not in line.value_ids:
                raise ValidationError(
                    self.env._(
                        "Default values for each attribute line must exist in "
                        "the attribute values (%(attr_name)s: %(default_val)s)",
                        **{
                            "attr_name": line.attribute_id.name,
                            "default_val": line.default_val.name,
                        },
                    )
                )

    @api.constrains("active", "value_ids", "attribute_id")
    def _check_valid_values(self):
        """Overwrite to save attribute line without
        values when custom is true"""
        for ptal in self:
            # Customization
            if ptal.active and not ptal.value_ids and not ptal.custom:
                # Old code
                # if ptal.active and not ptal.value_ids:
                # Customization End
                raise ValidationError(
                    self.env._(
                        "The attribute %(attr)s must have at least one value for "
                        "the product %(product)s.",
                        **{
                            "attr": ptal.attribute_id.display_name,
                            "product": ptal.product_tmpl_id.display_name,
                        },
                    )
                )
            for pav in ptal.value_ids:
                if pav.attribute_id != ptal.attribute_id:
                    raise ValidationError(
                        self.env._(
                            "On the product %(product)s you cannot associate the "
                            "value %(value)s with the attribute %(attr)s because they "
                            "do not match.",
                            **{
                                "product": ptal.product_tmpl_id.display_name,
                                "value": pav.display_name,
                                "attr": ptal.attribute_id.display_name,
                            },
                        )
                    )
        return True

    def _configurator_value_ids(self):
        """Values accepted for template attribute lines in `self`."""
        values = self.value_ids
        if any(self.mapped("custom")):
            values += self.env["product.config.session"].get_custom_value_id()
        return values


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

    def init(self):
        """Unicité `(attribut, nom)` EN BASE — D-081, condition 2.

        ⚠️ Aucun verrou applicatif ne remplace celle-ci : « je cherche, sinon je
        crée » laisse passer deux clients simultanés, et le stock se coupe en
        deux. Odoo n'en pose AUCUNE sur ce modèle.

        Deux détails qui ne sont pas des détails :
        · `name` est **traduit**, donc stocké en `jsonb`. L'index porte sur le
          terme source (`name->>'en_US'`) et non sur l'objet entier : sinon
          traduire une valeur en ferait une valeur différente, et le doublon
          repasserait ;
        · `WHERE active is true` — le ménage ARCHIVE (D-082), et une largeur
          archivée ne doit pas empêcher la même largeur de revivre.
        """
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS product_attribute_value_name_unique
            ON %s (attribute_id, (name->>'en_US')) WHERE active is true
            """
            % self._table
        )

    @api.model_create_multi
    def create(self, vals_list):
        """Range le nombre, et pose la séquence — D-081, conditions 2 et 3.

        ⚠️ Sans la séquence, les largeurs s'afficheraient **dans l'ordre où
        elles ont été vendues** : les valeurs se trient par `sequence` puis par
        id, et celles créées à la volée vaudraient toutes zéro. Le nombre
        lui-même fait une séquence.
        """
        for vals in vals_list:
            attribute = self.env["product.attribute"].browse(vals.get("attribute_id"))
            name = vals.get("name")
            if not attribute or not isinstance(name, str):
                continue
            if not attribute._is_numeric_custom():
                continue
            vals["name"] = name = attribute.canonical_custom_value(name)
            if not vals.get("sequence"):
                try:
                    vals["sequence"] = int(round(float(name)))
                except (TypeError, ValueError):
                    pass
        return super().create(vals_list)

    @api.autovacuum
    def _gc_configurator_values(self):
        """Archive les largeurs créées par le configurateur et jamais servies.

        ⚠️ **D-082 est à corriger sur la forme** : elle annonce « toute méthode
        nommée `_gc_*` » — c'était vrai jusqu'aux versions précédentes. En
        Odoo 18, `ir.autovacuum` ne collecte plus par le NOM mais par le
        décorateur `@api.autovacuum` (`ir_autovacuum.py:34`). Une méthode juste
        nommée `_gc_…` ne serait jamais appelée, et **rien ne le dirait**.

        Le critère de D-082 est « créée il y a plus de N jours ET jamais
        employée ». « Jamais employée » se lit ici **n'est portée par aucune
        variante** : puisque rien n'est résolu avant le devis (D-082), une
        valeur sans variante n'a jamais servi à vendre quoi que ce soit. Le
        détour par les lignes de vente, les mouvements de stock et les
        nomenclatures est donc inutile — et il aurait obligé le cœur du module
        à connaître `sale` et `mrp`, qu'il ne dépend pas.

        ⚠️ On ARCHIVE, on ne supprime pas : `product.template.attribute.value`
        référence la valeur en `ondelete='restrict'`, et l'historique doit
        rester lisible.
        """
        days = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("product_configurator_fa.value_gc_days", 90)
        )
        candidates = self.sudo().search(
            [
                ("configurator_generated", "=", True),
                ("create_date", "<", fields.Datetime.now() - timedelta(days=days)),
            ]
        )
        if not candidates:
            return
        ptavs = (
            self.env["product.template.attribute.value"]
            .sudo()
            .with_context(active_test=False)
            .search([("product_attribute_value_id", "in", candidates.ids)])
        )
        served = ptavs.filtered("ptav_product_variant_ids").product_attribute_value_id
        for value in candidates - served:
            for ptav in ptavs.filtered(
                lambda p, value=value: p.product_attribute_value_id == value
            ):
                line = ptav.attribute_line_id
                # Une ligne non personnalisable doit garder au moins une valeur
                # (`_check_valid_values`) : mieux vaut laisser la largeur en
                # place que casser le produit pour faire du ménage.
                if len(line.value_ids) > 1 or line.custom:
                    line.write({"value_ids": [(3, value.id)]})
            value.active = False

    def copy(self, default=None):
        """Add ' (Copy)' in name to prevent attribute
        having same name while copying"""
        if not default:
            default = {}
        default.update({"name": self.name + " (copy)"})
        product = super().copy(default)
        return product

    active = fields.Boolean(
        default=True,
        help="By unchecking the active field you can "
        "disable a attribute value without deleting it",
    )
    product_id = fields.Many2one(comodel_name="product.product")
    image = fields.Binary(
        attachment=True,
        help="Attribute value image (Display on website for radio buttons)",
    )

    @api.model
    def get_attribute_value_extra_prices(
        self, product_tmpl_id, pt_attr_value_ids, pricelist=None
    ):
        extra_prices = {}
        if not pricelist:
            pricelist = self.env.user.partner_id.property_product_pricelist

        related_product_av_ids = self.env["product.attribute.value"].search(
            [("id", "in", pt_attr_value_ids.ids), ("product_id", "!=", False)]
        )
        extra_prices = {
            av.id: av.product_id.with_context(
                pricelist=pricelist.id
            )._get_contextual_price()
            for av in related_product_av_ids
        }
        remaining_av_ids = pt_attr_value_ids - related_product_av_ids
        pe_lines = self.env["product.template.attribute.value"].search(
            [
                ("product_attribute_value_id", "in", remaining_av_ids.ids),
                ("product_tmpl_id", "=", product_tmpl_id),
            ]
        )
        for line in pe_lines:
            attr_val_id = line.product_attribute_value_id
            if attr_val_id.id not in extra_prices:
                extra_prices[attr_val_id.id] = 0
            extra_prices[attr_val_id.id] += line.price_extra
        return extra_prices

    def get_attribute_value_rates_sqm(self, product_tmpl_id, pt_attr_value_ids):
        """Les taux au m² de ces valeurs, sur ce produit — `{id de valeur: taux}`.

        Ne rend que les valeurs dont la LIGNE est au mètre carré : un taux saisi
        sur une ligne repassée au forfait ne doit pas ressurgir dans un libellé.

        ⚠️ UNE requête pour tout le lot, là où le calcul des forfaits voisin en
        fait une par valeur : `display_name` se calcule par paquets entiers dans
        une liste, et c'est exactement là qu'une requête par ligne se paie.
        """
        if not product_tmpl_id or not pt_attr_value_ids:
            return {}
        lines = self.env["product.template.attribute.value"].search(
            [
                ("product_tmpl_id", "=", product_tmpl_id),
                ("product_attribute_value_id", "in", pt_attr_value_ids.ids),
                ("price_extra_sqm", "!=", 0),
            ]
        )
        return {
            line.product_attribute_value_id.id: line.price_extra_sqm
            for line in lines
            if line.attribute_line_id.price_mode == "per_sqm"
        }

    def _compute_display_name(self):
        # useless return to make pylint happy
        res = super()._compute_display_name()
        if not self.env.context.get("show_price_extra"):
            return res
        product_template_id = self.env.context.get("active_id", False)
        price_precision = self.env["decimal.precision"].precision_get("Product Price")
        rates = self.get_attribute_value_rates_sqm(product_template_id, self)
        # La surface vient de l'INTERFACE, qui seule connaît la configuration en
        # cours : `product.config.session.get_config_surface()`. Absente, on
        # affiche le taux — c'est le cas du back-office, où aucune cote n'est
        # saisie, et l'assistant d'OCA ne la fournira pas (D-097 l'abandonne).
        surface = self.env.context.get("configurator_surface") or 0.0
        for attribute in self:
            extra_prices = attribute.get_attribute_value_extra_prices(
                product_tmpl_id=product_template_id, pt_attr_value_ids=attribute
            )
            price_extra = extra_prices.get(attribute.id)
            rate = rates.get(attribute.id)
            if rate and surface:
                # La surface est connue : le client voit ce que ÇA lui coûte,
                # sans avoir à multiplier (arbitrage Gerry, 2026-08-23).
                amount = rate * surface
                name = f"{attribute.name} ( +{amount:.{price_precision}f} )"
                attribute.display_name = name
            elif rate:
                # ⚠️ Pas encore de surface — les cotes ne sont pas toutes
                # saisies. On rend le TAUX, qui reste juste, plutôt qu'un
                # montant calculé sur une surface qu'on ne connaît pas. Et sans
                # le « /m² », « +25 » se lirait comme vingt-cinq euros, quand le
                # client d'une porte de 5 m² en paiera cent vingt-cinq.
                name = f"{attribute.name} ( +{rate:.{price_precision}f} /m² )"
                attribute.display_name = name
            elif price_extra:
                name = f"{attribute.name} ( +{price_extra:.{price_precision}f} )"
                attribute.display_name = name

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Use name_search as a domain restriction for the frontend to show
        only values set on the product template taking all the configuration
        restrictions into account.

        TODO: This only works when activating the selection not when typing
        """
        product_tmpl_id = self.env.context.get("_cfg_product_tmpl_id")
        if product_tmpl_id:
            # TODO: Avoiding browse here could be a good performance enhancer
            product_tmpl = self.env["product.template"].browse(product_tmpl_id)
            tmpl_vals = product_tmpl.attribute_line_ids.mapped("value_ids")
            attr_restrict_ids = []
            preset_val_ids = []
            new_args = []
            for arg in args:
                # Restrict values only to value_ids set on product_template
                if arg[0] == "id" and arg[1] == "not in":
                    preset_val_ids = arg[2]
                    # TODO: Check if all values are available for configuration
                else:
                    new_args.append(arg)
            val_ids = set(tmpl_vals.ids)
            if preset_val_ids:
                val_ids -= set(arg[2])
            val_ids = self.env["product.config.session"].values_available(
                val_ids, preset_val_ids, product_tmpl_id=product_tmpl_id
            )
            new_args.append(("id", "in", val_ids))
            mono_tmpl_lines = product_tmpl.attribute_line_ids.filtered(
                lambda line: not line.multi
            )
            for line in mono_tmpl_lines:
                line_val_ids = set(line.mapped("value_ids").ids)
                if line_val_ids & set(preset_val_ids):
                    attr_restrict_ids.append(line.attribute_id.id)
            if attr_restrict_ids:
                new_args.append(("attribute_id", "not in", attr_restrict_ids))
            args = new_args
        res = super().name_search(name=name, args=args, operator=operator, limit=limit)
        return res

    # TODO: Prevent unlinking custom options by overriding unlink

    # _sql_constraints = [
    #    ('unique_custom', 'unique(id,allow_custom_value)',
    #    'Only one custom value per dimension type is allowed')
    # ]


class ProductAttributeCustomValue(models.Model):
    """La valeur numérique qui a quitté la session pour la VARIANTE.

    ⚠️ Le cœur d'Odoo affiche « Largeur: 2400 » et perd l'unité que la session
    savait montrer (`product_config.py`, `_compute_val_name`) : la même valeur
    se lisait donc avec son unité pendant la configuration et sans elle sur le
    devis. Une seule règle, partout — la valeur est le nombre, l'affichage
    porte l'unité.
    """

    _inherit = "product.attribute.custom.value"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ptav_id = vals.get("custom_product_template_attribute_value_id")
            if "custom_value" in vals and ptav_id:
                attribute = (
                    self.env["product.template.attribute.value"]
                    .browse(ptav_id)
                    .attribute_id
                )
                vals["custom_value"] = attribute.canonical_custom_value(
                    vals["custom_value"]
                )
        return super().create(vals_list)

    def write(self, vals):
        if "custom_value" not in vals:
            return super().write(vals)
        result = True
        for ptav, records in self.grouped(
            "custom_product_template_attribute_value_id"
        ).items():
            canonical = dict(
                vals,
                custom_value=ptav.attribute_id.canonical_custom_value(
                    vals["custom_value"]
                ),
            )
            result = (
                super(ProductAttributeCustomValue, records).write(canonical) and result
            )
        return result

    @api.depends(
        "custom_product_template_attribute_value_id.attribute_id.uom_id",
        "custom_product_template_attribute_value_id.attribute_id.custom_type",
    )
    def _compute_name(self):
        super()._compute_name()
        for record in self:
            attribute = record.custom_product_template_attribute_value_id.attribute_id
            if not attribute.uom_id or not record.custom_value:
                continue
            label = record.custom_product_template_attribute_value_id.display_name
            shown = attribute.format_custom_value(record.custom_value)
            record.name = f"{label}: {shown}" if label else shown


class ProductAttributePrice(models.Model):
    _inherit = "product.template.attribute.value"
    # Leverage product.template.attribute.value to compute the extra weight
    # each attribute adds

    weight_extra = fields.Float(string="Attribute Weight Extra", digits="Stock Weight")
    # Exposé pour les VUES seulement : le mode vit sur la ligne, mais c'est la
    # valeur qu'on édite, et une colonne ne peut pas se cacher sur un champ
    # qu'elle ne porte pas.
    price_mode = fields.Selection(
        related="attribute_line_id.price_mode", string="Extra Price Mode", readonly=True
    )
    price_extra_sqm = fields.Float(
        string="Extra Price per m²",
        digits="Product Price",
        help="Rate applied to the surface of the product (grid axis X × axis Y) "
        "when the attribute line is priced per square meter",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Le taux du CATALOGUE devient celui du produit, sauf mention contraire.

        Odoo fait déjà ce geste pour `price_extra`
        (`product_template_attribute_line.py:244`) mais ne connaît pas notre
        taux : sans cette recopie, la valeur créée pour un produit repartirait à
        zéro et le nuancier ne servirait de défaut à rien (D-162).
        """
        for vals in vals_list:
            if "price_extra_sqm" in vals or not vals.get("product_attribute_value_id"):
                continue
            value = self.env["product.attribute.value"].browse(
                vals["product_attribute_value_id"]
            )
            if value.default_extra_price_sqm:
                vals["price_extra_sqm"] = value.default_extra_price_sqm
        return super().create(vals_list)


class ProductAttributeValueLine(models.Model):
    _name = "product.attribute.value.line"
    _description = "Product Attribute Value Line"
    _order = "sequence"

    sequence = fields.Integer(default=10)
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product Template",
        ondelete="cascade",
        required=True,
    )
    value_id = fields.Many2one(
        comodel_name="product.attribute.value",
        required=True,
        string="Attribute Value",
    )
    attribute_id = fields.Many2one(
        comodel_name="product.attribute", related="value_id.attribute_id"
    )
    value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        relation="product_attribute_value_product_attribute_value_line_rel",
        column1="product_attribute_value_line_id",
        column2="product_attribute_value_id",
        string="Values Configuration",
    )
    product_value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        relation="product_attr_values_attr_values_rel",
        column1="product_val_id",
        column2="attr_val_id",
        compute="_compute_get_value_id",
        store=True,
    )

    @api.depends(
        "product_tmpl_id",
        "product_tmpl_id.attribute_line_ids",
        "product_tmpl_id.attribute_line_ids.value_ids",
    )
    def _compute_get_value_id(self):
        for attr_val_line in self:
            template = attr_val_line.product_tmpl_id
            value_list = template.attribute_line_ids.mapped("value_ids")
            attr_val_line.product_value_ids = [(6, 0, value_list.ids)]

    @api.constrains("value_ids")
    def _validate_configuration(self):
        """Ensure that the passed configuration in value_ids is a valid"""
        cfg_session_obj = self.env["product.config.session"]
        for attr_val_line in self:
            value_ids = attr_val_line.value_ids.ids
            value_ids.append(attr_val_line.value_id.id)
            valid = cfg_session_obj.validate_configuration(
                value_ids=value_ids,
                product_tmpl_id=attr_val_line.product_tmpl_id.id,
                final=False,
            )
            if not valid:
                raise ValidationError(
                    self.env._(
                        "Values provided to the attribute value line are "
                        "incompatible with the current rules"
                    )
                )
