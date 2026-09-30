from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Les formes qui montrent une IMAGE, et celles qu'une ligne résumé peut remplacer (D-382).
IMAGE_FORMS = ("card", "swatch")
SUMMARY_FORMS = ("card", "swatch", "radio", "pills", "select")


class ProductAttributeLine(models.Model):
    """La VUE 3D que le configurateur affiche pour cet attribut — D-163.

    ⚠️ Ce champ ne peut pas vivre dans le cœur du configurateur : il pointe une
    caméra de `product_editor`, et l'y poser forcerait le cœur AGPL-3 à dépendre
    de l'éditeur LGPL-3 — l'inverse du sens que D-075 protège. C'est le module
    d'interface qui les réunit, et lui seul.
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

    def _resolve_view_camera(self, step_line=None):
        """La vue à montrer : celle de l'attribut, sinon celle de l'étape, sinon RIEN.

        ⚠️ « Rien » ne veut pas dire « la vue par défaut » : la caméra **ne bouge
        pas** (arbitrage Gerry). Le client garde le cadrage qu'il s'est donné ;
        une vue déclarée l'impose, l'absence de vue le laisse tranquille. C'est
        le précédent de D-125 dans l'éditeur — trois travaux imposent leur vue,
        et rendent le réglage en partant.
        """
        self.ensure_one()
        if self.view_camera_id:
            return self.view_camera_id
        if step_line:
            return step_line.view_camera_id
        return self.env["product.model3d.camera"]


class ProductAttribute(models.Model):
    """Le type « matière » — l'attribut dont les valeurs désignent une FICHE.

    ⚠️ Il vit ICI et non dans le cœur du configurateur, pour la même raison que
    `view_camera_id` : il pointe `product.model3d.material`, un modèle de
    `product_editor`. ⓘ **Mais pas pour la raison que ce fichier avançait
    jusqu'ici.** Le commentaire de `view_camera_id` invoque la licence — *« forcer
    le cœur AGPL-3 à dépendre de l'éditeur LGPL-3, l'inverse du sens que D-075
    protège »* — et D-075 dit précisément le contraire : *« configurateur | AGPL-3
    | fork OCA + moteur de l'éditeur (LGPL-3, compatible) […] la LGPL-3 étant
    compatible avec l'AGPL-3, l'architecture tient »*. Ce que D-075 interdit, c'est
    l'ÉDITEUR dépendant du configurateur, et un configurateur AGPL s'appuyant sur
    du propriétaire.

    La vraie raison est la **MODULARITÉ** : un configurateur sans éditeur 3D doit
    continuer de fonctionner. Ce module, lui, dépend déjà des deux.

    ─ Pourquoi une fiche et non une couleur ──────────────────────────────────

    Une matière dépend de la pièce (D-166) : « RAL 7016 » n'est pas la même fiche
    sur une poignée d'alu et sur un panneau d'acier. La piste d'un attribut
    désignant une COULEUR du nuancier, la zone dérivant sa fiche de *(sa matière
    modèle × la couleur)*, a donc été explorée — et écartée par Gerry le
    2026-08-28 : *« c'est plus que couleur ; si on choisit du bois, un métal ou une
    finition de laquage, cela se voit dans la miniature. La miniature de la matière
    sert à la sélection. »* Un code couleur ne montre ni le fil du bois ni le
    brossé du métal ; seule une fiche porte une `preview_image`.

    ⚠️ Le cas de D-166 ne disparaît pas — il se DÉPLACE. Une fiche « alu satiné »
    ne s'applique pas à un panneau d'acier, et la réponse n'est plus une table de
    correspondance mais **une question par famille de support** : la zone désigne
    déjà la sienne (`driver_attribute_id`), et une porte peut demander sa teinte
    intérieure et sa teinte extérieure à la fois.

    C'est alors, exactement, le patron de la face support : *« the attribute brings
    the products which may be laid here […] the support keeps NO list of its own »*.
    """

    _inherit = "product.attribute"

    # ⚠️ **« Matière » n'est PLUS ajouté ici**, il est dans la liste de base de
    # `product_attribute_advanced` (2026-09-02). Ce module est le pont entre le
    # configurateur et l'éditeur ; or c'est l'ÉDITEUR qui a besoin de cette valeur — il
    # ne propose comme pilote de zone que les questions qui portent sur une matière — et
    # il ne peut pas dépendre d'un pont AGPL-3 (D-075). La laisser ici la rendait donc
    # inatteignable pour son premier usager.
    #
    # ⓘ Ce qui RESTE ici est le lien réel : la valeur qui pointe une fiche matière. Une
    # valeur de sélection ne nomme aucun modèle et n'entraîne aucune dépendance ; un
    # `Many2one` vers `product.model3d.material`, si.

    # ── LES FORMES D'AFFICHAGE SONT À CE MODULE — D-258, arbitré 2026-09-06 ──
    #
    # Odoo en propose cinq — radio, pastilles, liste, couleur, cases — et aucune ne
    # montre une IMAGE. Or une réponse qui désigne un produit ou une matière se
    # reconnaît à sa forme avant de se lire : la CARTE est un carré à coins
    # arrondis portant la vignette, le libellé dessous.
    #
    # ⓘ **Pourquoi ici et pas dans `product_attribute_advanced`**, où elle avait
    # d'abord été posée. Ce module-là dit ce qu'une question EST — ce qu'une
    # valeur désigne, comment elle se lit, dans quelle unité — et sa notice
    # écarte explicitement le dessin : *« il ne porte aucun WIDGET »*. Une forme
    # d'affichage est du dessin, et c'est ce module-ci qui dessine. Les formes à
    # venir s'ajoutent donc ICI, à côté du gabarit qui les rend.
    #
    # ⓘ Ajoutée au champ du CŒUR plutôt que doublée par un réglage à nous : deux
    # façons de dire « comment cette question s'affiche » finiraient par se
    # contredire, faute que ce dépôt a déjà payée (`nature` contre `value_type`,
    # 2026-09-02).
    #
    # ⚠️ **ODOO NE SAIT PAS LA RENDRE.** `website_sale.variants` branche en
    # `t-if`/`t-elif` sur ses cinq chaînes, sans `t-else` : une carte disparaît de
    # SES pages, sans erreur (rattrapé par `variants_card_fallback` côté
    # boutique). Et son dialogue de vente est pire : il VALIDE `display_type`
    # contre une liste fermée puis choisit son gabarit par un `switch` sans
    # `default`. ⏳ Non traité — il y faut un module-pont dépendant de `sale`.
    # ⓘ **LA GRANDE PASTILLE** (demande de Gerry, 2026-09-29) : un disque illustré de la
    # matière ou de la teinte, son nom dessous — la « Couleur » d'Odoo en plus grand et
    # nommée, parce que 32 px ne montrent pas un bois. Mêmes deux rustines que la carte :
    # la boutique la rend en « Couleur » (`variants_card_fallback`), le dialogue de vente
    # l'accepte (`sale_card_tolerance.js`).
    display_type = fields.Selection(
        selection_add=[("card", "Card"), ("swatch", "Large swatch")],
        ondelete={"card": "set default", "swatch": "set default"},
    )
    # ⓘ **LA MARQUE DU CHOIX d'une grande pastille** — l'anneau OU la coche, jamais les deux
    # (Gerry, 2026-09-29 : « les deux ne vont pas ensemble »). Sur l'ATTRIBUT (option A) :
    # la coche pour des bois, l'anneau pour une texture dont elle cacherait le détail.
    swatch_mark = fields.Selection(
        selection=[("check", "Checkmark"), ("ring", "Ring")],
        default="check",
        required=True,
        string="Selection mark",
        help="How a large swatch shows that it is chosen: a checkmark in its centre, or a "
        "ring around it. The name below turns bold in both cases.",
    )
    # ⓘ **LA TAILLE d'une carte ou d'une grande pastille** — D-382 (Gerry, 2026-09-30 :
    # « plutôt modifier la taille que le nombre en largeur »). Le nombre par ligne en
    # découle, selon la place. `medium` est l'affichage d'avant ce champ : un attribut
    # existant ne bouge pas d'un pixel.
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
    # formes à image ; `summary` aussi pour les boutons et la liste (Gerry, 2026-09-30).
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

    **Pourquoi la MATIÈRE et non la teinte du nuancier.** Les deux modèles
    existent — `product.model3d.color` porte un hexa et un code RAL,
    `product.model3d.material` porte un rendu PBR. Arbitrage de Gerry
    (2026-08-28) : *« il pointe la miniature pbr »*, ce qui prolonge ce qu'il
    avait dit du nuancier — *« c'est plus que couleur : si on choisit du bois, un
    métal ou une finition de laquage, cela se voit dans la miniature »*. Une
    essence de chêne n'a pas de code hexadécimal.

    ⚠️ **Et la miniature n'est pas RECOPIÉE.** `material_preview` est un champ
    `related` en lecture seule : l'image reste celle du catalogue, régénérée à
    chaque enregistrement de la matière. La copier ici la ferait diverger à la
    première retouche, et le catalogue cesserait d'être la source. Arbitré :
    *« celle de la matière en lecture seule »*.

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
        string="Preview",
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
        `material_id` : il pointe une fiche de l'éditeur, et le nommer ferait
        dépendre l'AGPL-3 de celui-ci (D-075).
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
