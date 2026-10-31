# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La carte, la grande pastille et la couleur illustrée sur la fiche d'un produit ORDINAIRE — D-563."""
import base64
import re

from odoo import Command
from odoo.tests import HttpCase, tagged

# Un PNG d'un pixel : une image posée sur la valeur, premier maillon de `_preview_source` (D-258).
PIXEL = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cf0000000301010018dd8db40000000049454e44ae426082"))


@tagged("post_install", "-at_install")
class ImageFormsOnTheShop(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # ⚠️ La « Liste des variantes » remplace les sélecteurs. Sur fabk18, c'est la copie du SITE qui est active,
        # pas la vue générique : il faut les désactiver toutes, par leur clé.
        env["ir.ui.view"].with_context(active_test=False).search(
            [("key", "=", "website_sale.product_variants")]).active = False

        def attribute(name, display_type, *values, **extra):
            record = env["product.attribute"].create(
                {"name": name, "display_type": display_type, "create_variant": "always", **extra})
            return record, env["product.attribute.value"].create(
                [{"name": v, "attribute_id": record.id} for v in values])

        cls.plate, cls.plates = attribute("Plaque Sigma", "card", "Carbone Sigma", "Alu Sigma",
                                          answer_size="small")
        cls.finish, cls.finishes = attribute("Finition Sigma", "swatch", "Chene Sigma", "Noyer Sigma",
                                             swatch_mark="ring")
        cls.tint, cls.tints = attribute("Teinte Sigma", "color", "Bleu Sigma", "Rouge Sigma")
        (cls.plates[0] | cls.finishes[0] | cls.tints[0]).image = PIXEL
        cls.tmpl = env["product.template"].create({
            "name": "Support Sigma", "list_price": 10.0, "is_published": True,
            "attribute_line_ids": [
                Command.create({"attribute_id": a.id, "value_ids": [Command.set(v.ids)]})
                for a, v in ((cls.plate, cls.plates), (cls.finish, cls.finishes), (cls.tint, cls.tints))],
        })

    def _html(self):
        return self.url_open(self.tmpl.website_url).text

    def test_la_vignette_n_existe_que_si_la_valeur_en_a_une(self):
        self.assertEqual(self.plates[0]._preview_url(), "/configurator/value/%s/image" % self.plates[0].id)
        self.assertFalse(self.plates[1]._preview_url())

    def test_la_carte_est_dessinee_comme_au_configurateur(self):
        html = self._html()
        self.assertIn("o_cfg3d_cards o_cfg3d_cards--small", html)
        self.assertIn('class="o_cfg3d_card_shot"', html)
        self.assertIn('src="/configurator/value/%s/image"' % self.plates[0].id, html)
        self.assertNotIn("o_variant_pills", html)          # plus de repli sur les pastilles de texte

    def test_la_grande_pastille_porte_sa_marque_et_sa_taille(self):
        html = self._html()
        self.assertIn("o_cfg3d_bigswatches o_cfg3d_bigswatches--ring o_cfg3d_bigswatches--medium", html)
        self.assertIn('src="/configurator/value/%s/image"' % self.finishes[0].id, html)
        # Anneau choisi : pas de coche rendue.
        self.assertNotIn("o_cfg3d_bigswatch_check", html)

    def test_chaque_reponse_reste_un_choix_lu_par_odoo(self):
        html = self._html()
        ptav = self.tmpl.attribute_line_ids.filtered(
            lambda line: line.attribute_id == self.finish).product_template_value_ids[1]
        self.assertRegex(html, r'<input type="radio" class="visually-hidden js_variant_change always"[^>]*'
                               r'value="%s"' % ptav.id)

    def test_la_couleur_montre_l_image_de_la_valeur(self):
        html = self._html()
        self.assertIn("background:url(/configurator/value/%s/image)" % self.tints[0].id, html)
        # Le témoin : la valeur sans image garde le rendu du cœur.
        self.assertTrue(re.search(r'style="background:Rouge Sigma"', html))

    def test_le_dialogue_de_vente_recoit_la_forme_et_la_vignette(self):
        """Par la route du dialogue : la classe de contrôleur servie est celle qu'Odoo fusionne."""
        self.authenticate("admin", "admin")
        info = self.make_jsonrpc_request("/sale/product_configurator/get_values", {
            "product_template_id": self.tmpl.id, "quantity": 1,
            "currency_id": self.env.company.currency_id.id, "so_date": "2026-10-31 00:00:00",
        })["products"][0]
        lines = {line["attribute"]["name"]: line for line in info["attribute_lines"]}
        finish = lines["Finition Sigma"]
        self.assertEqual(finish["attribute"]["swatch_mark"], "ring")
        self.assertEqual(lines["Plaque Sigma"]["attribute"]["answer_size"], "small")
        previews = [v["preview"] for v in finish["attribute_values"]]
        self.assertEqual(previews, ["/configurator/value/%s/image" % self.finishes[0].id, False])
