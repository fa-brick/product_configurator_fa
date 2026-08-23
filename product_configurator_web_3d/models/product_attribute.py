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
