"""Ce qu'exécute `sale.order.line` (BLL, D-541).

Le PLAN COTÉ d'une ligne de devis (W-118, lot 6, D-468).

Les pages viennent du modèle de document du produit (`drawing_template_id`), dessinées par le
moteur dans Node pour LA configuration de la ligne.

⚠️ Tant que le devis se modifie, les pages se recalculent à chaque lecture : un plan gelé trop tôt montrerait une configuration que le client a changée depuis (D-468).
⚠️ Confirmé, le devis lit le GEL de sa ligne et ne recalcule plus : un modèle 3D retouché après la commande changerait le plan de ce qui est vendu (D-468).
"""
import json
from markupsafe import Markup
from odoo import models


#: Le nom de la pièce jointe qui porte le gel d'une ligne.
FROZEN_NAME = "drawing_pages.json"


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _drawing_template(self):
        """Le modèle de document du produit de la ligne, ou rien — une note, une section n'en ont pas."""
        self.ensure_one()
        if self.display_type:
            return self.env["drawing.template"]
        template = self.product_id.product_tmpl_id.sudo().drawing_template_id
        return template if template.page_ids else self.env["drawing.template"]

    def _drawing_values(self):
        """Les réponses de la configuration de la ligne, à la forme du moteur.

        ⚠️ Sans session (un article choisi tel quel), les réponses viennent de la VARIANTE : la configuration par défaut dessinerait un autre produit que celui vendu.
        ⚠️ Une question NUMÉRIQUE reçoit le NOM de la valeur, jamais son identifiant — la règle de `_web_values` ([[L-219]]).
        """
        self.ensure_one()
        session = self.config_session_id.sudo()
        if session:
            return session._web_values(), session._web_link_answers()
        ptavs = self.product_id.product_template_attribute_value_ids | self.product_no_variant_attribute_value_ids
        values = {}
        for value in ptavs.product_attribute_value_id:
            values[value.attribute_id.id] = value.name if value.attribute_id.is_numeric() else value.id
        return values, {}

    def _drawing_compute(self):
        """Les pages du plan, calculées maintenant : `[{svg, width, height}]`, `[]` s'il n'y a rien à
        dessiner, `None` si le moteur a échoué."""
        self.ensure_one()
        template = self._drawing_template()
        product = self.product_id.product_tmpl_id.sudo()
        model3d = product._root_model3d() if template else None
        if not model3d:
            return []
        values, link_answers = self._drawing_values()
        lang = self.order_id._get_lang() or self.env.lang
        # ⓘ Les légendes dans la langue du CLIENT, comme le reste du devis.
        spec = template.with_context(lang=lang)._engine_pages(product)
        answer = model3d._render_drawing(model3d.to_definition(values, link_answers=link_answers),
                                         model3d.get_attribute_scope(values), spec, lang=lang)
        if not answer or len(answer["pages"]) != len(spec):
            return None
        return [{"svg": page["svg"], "width": wanted["width"], "height": wanted["height"]}
                for page, wanted in zip(answer["pages"], spec)]

    def _drawing_pages(self):
        """Les pages que le devis montre : le gel s'il existe, sinon le calcul (voir l'en-tête).

        ⓘ Un devis confirmé dont le gel a échoué (Node en panne) gèle à la lecture suivante qui réussit (D-468).
        """
        self.ensure_one()
        frozen = self.sudo().drawing_attachment_id
        if frozen:
            return json.loads(frozen.raw or b"{}").get("pages") or []
        pages = self._drawing_compute()
        if pages and self.order_id.state == "sale":
            self._drawing_store(pages)
        return pages

    def _drawing_store(self, pages):
        """Gèle les pages de la ligne dans une pièce jointe."""
        self.ensure_one()
        # ⚠️ En `sudo` : au portail, c'est le CLIENT qui accepte le devis, sans droit sur les pièces jointes.
        # ⚠️ Écrire `raw`, jamais `datas` : en Odoo 20, `datas` est ignoré et la pièce jointe naît vide ([[L-462]]).
        attachment = self.env["ir.attachment"].sudo().create({
            "name": FROZEN_NAME, "res_model": self._name, "res_id": self.id,
            "mimetype": "application/json", "raw": json.dumps({"pages": pages}).encode(),
        })
        self.sudo().drawing_attachment_id = attachment

    def _drawing_markup(self, page):
        """Le SVG d'une page, à insérer dans le portail.

        ⓘ Un SVG que le MOTEUR a écrit, ses textes échappés (`page_svg.js`) : il s'insère tel quel.
        """
        return Markup(page["svg"])
