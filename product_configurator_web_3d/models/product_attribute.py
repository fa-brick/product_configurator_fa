from odoo import fields, models


class ProductAttributeLine(models.Model):
    """La VUE 3D que le configurateur affiche pour cet attribut — D-163.

    ⚠️ Ce champ ne peut pas vivre dans le cœur du configurateur : il pointe une
    caméra de `product_editor`, et l'y poser forcerait le cœur AGPL-3 à dépendre
    de l'éditeur LGPL-3 — l'inverse du sens que D-075 protège. C'est le module
    d'interface qui les réunit, et lui seul.
    """

    _inherit = "product.template.attribute.line"

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
