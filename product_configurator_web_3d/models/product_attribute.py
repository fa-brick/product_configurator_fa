from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Les formes qui montrent une IMAGE, et celles qu'une ligne résumé peut remplacer (D-382).
IMAGE_FORMS = ("card", "swatch")
SUMMARY_FORMS = ("card", "swatch", "radio", "pills", "select")


class ProductAttributeLine(models.Model):
    """La VUE 3D que le configurateur affiche pour cet attribut — D-163.

    ⚠️ Ne pas le poser dans le cœur du configurateur : il pointe une caméra de
    `product_editor`, et le cœur en dépendrait (D-163).
    """

    _inherit = "product.template.attribute.line"

    def _configurator_camera_name(self):
        """Le crochet du cœur, rempli ici — la caméra est une fiche de l'éditeur."""
        self.ensure_one()
        return self.view_camera_id.display_name or ""

    def _configurator_camera_id(self):
        self.ensure_one()
        return self.view_camera_id.id or False

    def _configurator_set_camera(self, camera_id):
        """Posée depuis la liste déroulante de l'arbre (D-386)."""
        self.ensure_one()
        self.view_camera_id = self.product_tmpl_id._configurator_camera_of(camera_id)

    view_camera_id = fields.Many2one(
        comodel_name="product.model3d.camera",
        string="3D View",
        ondelete="set null",
        domain="[('model3d_id.product_tmpl_id', '=', product_tmpl_id)]",
        help="View shown while this attribute is being answered. Empty means "
        "the camera does not move.",
    )


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

    def _web_answer_layout(self):
        """La disposition EFFECTIVE, telle que la page la reçoit — D-382.

        ⓘ Le miroir de `answerLayoutOf` (`configurator_state.js`) : le serveur sert la
        disposition déjà ramenée à ce que la forme permet, la page refait le même calcul
        pour un serveur qui ne la servirait pas encore.
        """
        self.ensure_one()
        layout = self.answer_layout or "inline"
        if layout in ("scroll", "line") and self.display_type not in IMAGE_FORMS:
            return "inline"
        if layout == "summary" and self.display_type not in SUMMARY_FORMS:
            return "inline"
        return layout


class ProductAttributeValue(models.Model):
    """Une valeur peut DÉSIGNER une matière — et c'est sa miniature qui la choisit.

    ⚠️ **Le type « matière » ne désignait encore RIEN.** Il est arrivé comme un
    libellé du `Selection` ci-dessus : aucune colonne de la valeur ne pointait une
    fiche matière. Ce champ est le chaînon qui manquait.

    ⚠️ La MATIÈRE et non la teinte du nuancier (`product.model3d.color`) : une essence de
    chêne n'a pas de code hexadécimal (D-196).

    ⚠️ **La miniature n'est pas RECOPIÉE** : `material_preview` est un `related` en lecture
    seule ; une copie divergerait à la première retouche de la matière (D-196).

    ⓘ Le droit de lecture existe déjà : `product.model3d.material` est lisible par
    `base.group_user`, donc par tout utilisateur interne qui ouvre un attribut.
    """

    _inherit = "product.attribute.value"

    material_id = fields.Many2one(
        comodel_name="product.model3d.material",
        string="Material",
        # `restrict` et non `cascade` : une matière encore désignée par une valeur
        # de catalogue ne doit pas disparaître en silence — la valeur perdrait ce
        # qu'elle désigne sans que rien ne le dise.
        ondelete="restrict",
        index=True,
        help="The material this value stands for. Its preview is what the "
             "customer picks from.",
    )
    material_preview = fields.Image(
        related="material_id.preview_image",
        string="Material preview",
        readonly=True,
    )

    def _web_categories(self):
        """Les catégories sous lesquelles cette réponse se range au panneau de choix — D-382.

        Une liste de `{key, name, sequence, parent}`, la FEUILLE seulement : ici la catégorie
        de la MATIÈRE que la valeur désigne (un arbre depuis D-382, dans `product_editor`).
        La boutique y ajoute les catégories e-commerce du PRODUIT désigné, par surcharge
        (`product_configurator_web_sale`) : ce module ne dépend pas de `website_sale`.

        ⚠️ Clé PRÉFIXÉE par le modèle (`m5`) : deux modèles, deux séquences d'identifiants.
        Lu en `sudo`, comme le reste de l'état : le visiteur n'a aucun droit sur les matières.
        """
        self.ensure_one()
        category = self.sudo().material_id.category_id
        if not category:
            return []
        return [{
            "key": "m%s" % category.id,
            "name": category.name,
            "sequence": category.sequence,
            "parent": category.parent_id.name or "",
        }]

    def _preview_source(self):
        """La MATIÈRE complète la chaîne du module attribut — D-258.

        ⓘ Elle vient en DERNIER, et c'est voulu : l'image posée sur la valeur,
        puis le produit qu'elle désigne, puis seulement le rendu de sa matière.
        Une valeur ne désigne jamais les deux à la fois (D-219 les efface l'une
        l'autre), donc l'ordre ne tranche rien en pratique — il dit simplement
        que ce module AJOUTE une provenance sans déplacer les autres.
        """
        record, field = super()._preview_source()
        if record:
            return record, field
        if self.material_id and self.material_id.preview_image:
            return self.material_id, "preview_image"
        return None, None

    # ─ LA LIGNE SE REMPLIT SEULE — D-198 ────────────────────────────────────
    #
    # ⚠️ La miniature suivait déjà (elle est `related`) ; le NOM, non — et il est
    # requis. Choisir « Chêne » obligeait à retaper « Chêne » pour pouvoir
    # enregistrer. Le pendant exact de ce que le cœur fait pour le produit.
    #
    # Le nom personnalisé n'est jamais écrasé : voir le commentaire du cœur.
    @api.onchange("material_id")
    def _onchange_material_id_fills_the_name(self):
        if not self.material_id:
            return
        ancien = self._origin.material_id.display_name if self._origin.material_id else False
        if not self.name or self.name == ancien:
            self.name = self.material_id.display_name

    def _purge_designation(self, value_type):
        """Le crochet du cœur, complété : la matière s'efface aussi — D-219.

        ⓘ Chaque module efface ce qu'il a posé. Le cœur ne peut pas nommer
        `material_id` : il pointe une fiche de l'éditeur, dont le cœur ne dépend pas.
        """
        super()._purge_designation(value_type)
        if value_type != "material":
            self.filtered("material_id").material_id = False

    # ─ DEUX BARRIÈRES, comme partout ailleurs (D-080, D-194, D-196) ─────────
    @api.constrains("material_id")
    def _check_material_only_for_material_type(self):
        for value in self:
            if value.material_id and value.attribute_id.value_type != "material":
                raise ValidationError(
                    self.env._(
                        "Only an attribute whose values designate a Material can "
                        "point at one. Change the attribute's value type, or "
                        "clear the material."
                    )
                )
