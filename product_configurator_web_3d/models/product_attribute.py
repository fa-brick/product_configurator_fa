from odoo import api, fields, models
from odoo.exceptions import ValidationError


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

    # `ondelete` est EXIGÉ par Odoo sur un `selection_add` stocké : il dit ce que
    # deviennent les enregistrements qui portent la valeur si ce module part. Les
    # ramener au défaut vaut mieux que de les laisser pointer un type disparu.
    value_type = fields.Selection(
        selection_add=[("material", "Material")],
        ondelete={"material": "set default"},
    )


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
