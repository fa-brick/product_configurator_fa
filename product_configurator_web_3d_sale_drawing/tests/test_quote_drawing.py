# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Le PLAN COTÉ joint au devis (W-118, lot 6, D-468).

Ce qui est éprouvé : un devis en cours redessine le plan de SA configuration ; la commande le gèle,
et un plan gelé ne bouge plus ; une panne du moteur laisse passer la confirmation, se note sur le
devis, et le gel se retente à la lecture suivante ; une ligne sans configuration dessine SA variante ;
le PDF du devis reçoit les pages en queue, à l'échelle exacte ; le portail montre le plan sous la ligne.

⓵ Le moteur est SIMULÉ (`_render_drawing`) : ce qui est éprouvé ici, c'est le pont, pas le dessin.
"""
import io
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from PIL import Image

from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools.pdf import PdfFileReader

PORTRAIT_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">'
                '<line x1="10" y1="20" x2="110" y2="20" stroke="#000" stroke-width="0.5"/>'
                '<text x="10" y="40">{label}</text></svg>')
LANDSCAPE_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210">'
                 '<text x="10" y="40">{label}</text></svg>')


def _wkhtmltopdf_ok(env):
    return env["ir.actions.report"].get_wkhtmltopdf_state() == "ok"


class DrawingCommon:

    @classmethod
    def _fixture(cls):
        cls.attribute = cls.env["product.attribute"].create({"name": "Finition plan"})
        cls.oak, cls.ash = cls.env["product.attribute.value"].create([
            {"name": "Chêne", "attribute_id": cls.attribute.id},
            {"name": "Frêne", "attribute_id": cls.attribute.id},
        ])
        cls.drawing_template = cls.env["drawing.template"].create({"name": "Plan de porte"})
        portrait = cls.drawing_template.page_ids
        landscape = cls.env["drawing.page"].create({"template_id": cls.drawing_template.id,
                                                    "orientation": "landscape"})
        cls.env["drawing.frame"].create([
            {"page_id": portrait.id, "x": 10, "y": 10, "width": 90, "height": 90, "view": "front"},
            {"page_id": landscape.id, "x": 10, "y": 10, "width": 90, "height": 90, "view": "top"},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte cotée",
            "config_ok": True,
            "list_price": 100.0,
            "drawing_template_id": cls.drawing_template.id,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id,
                "value_ids": [Command.set((cls.oak | cls.ash).ids)],
            })],
        })
        cls.env["product.model3d"].create({"name": "Porte", "piece_type": "part", "product_tmpl_id": cls.tmpl.id})
        cls.partner = cls.env["res.partner"].create({"name": "Client du plan"})

    def _line(self, values, session=True):
        """Une ligne de devis de la porte, configurée par `values` — avec sa session, ou sans."""
        config = self.env["product.config.session"].create_get_session(self.tmpl.id, force_create=True)
        config.value_ids = [Command.set(values.ids)]
        variant = config.create_get_variant()
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": order.id, "product_id": variant.id, "product_uom_qty": 1,
            "config_session_id": config.id if session else False,
        })
        return line

    def _engine(self, answer=None):
        """Le moteur simulé : une page par page demandée, qui nomme la réponse reçue."""
        calls = []

        def render(model3d, definition, scope, pages, lang=None):
            calls.append({"scope": scope, "pages": pages, "lang": lang})
            if answer is not None:
                return answer(pages)
            label = ",".join(str(v) for v in sorted(scope.values(), key=str)) or "default"
            return {"pages": [{"svg": (LANDSCAPE_SVG if p["width"] > p["height"] else PORTRAIT_SVG).format(label=label),
                               "views": []} for p in pages], "warnings": [], "ms": 1}

        return patch.object(self.registry["product.model3d"], "_render_drawing", autospec=True,
                            side_effect=render), calls


@tagged("post_install", "-at_install")
class TestQuoteDrawing(DrawingCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()

    def test_un_devis_en_cours_redessine_sa_configuration(self):
        line = self._line(self.oak)
        engine, calls = self._engine()
        with engine:
            first = line.order_id._drawing_pages()
            line.config_session_id.value_ids = [Command.set(self.ash.ids)]
            second = line.order_id._drawing_pages()
        self.assertEqual([(p["width"], p["height"]) for p in first], [(210.0, 297.0), (297.0, 210.0)])
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(first[0]["svg"], second[0]["svg"])
        self.assertFalse(line.drawing_attachment_id)

    def test_la_commande_gele_le_plan_qui_ne_bouge_plus(self):
        line = self._line(self.oak)
        engine, calls = self._engine()
        with engine:
            line.order_id.action_confirm()
            frozen = line.drawing_attachment_id
            self.assertTrue(frozen)
            self.assertGreater(frozen.file_size, 0)
            before = line.order_id._drawing_pages()
            line.config_session_id.value_ids = [Command.set(self.ash.ids)]
            after = line.order_id._drawing_pages()
        self.assertEqual(len(calls), 1)
        self.assertEqual(before, after)
        self.assertEqual(len(after), 2)

    def test_une_panne_du_moteur_ne_bloque_pas_la_commande(self):
        line = self._line(self.oak)
        order = line.order_id
        engine, _calls = self._engine(answer=lambda pages: None)
        with engine, self.assertLogs("odoo.addons.product_configurator_web_3d_sale_drawing", level="ERROR"):
            order.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertFalse(line.drawing_attachment_id)
        self.assertIn("could not be drawn", order.message_ids[:1].body)
        # ⓘ Le moteur revenu, la lecture suivante GÈLE.
        engine, _calls = self._engine()
        with engine:
            self.assertEqual(len(order._drawing_pages()), 2)
        self.assertTrue(line.drawing_attachment_id)

    def test_sans_session_la_ligne_dessine_sa_variante(self):
        line = self._line(self.ash, session=False)
        engine, calls = self._engine()
        with engine:
            line._drawing_pages()
        self.assertIn(self.ash.id, calls[0]["scope"].values())

    def test_un_produit_sans_modele_de_document_n_a_pas_de_plan(self):
        line = self._line(self.oak)
        self.tmpl.drawing_template_id = False
        engine, calls = self._engine()
        with engine:
            self.assertEqual(line.order_id._drawing_pages(), [])
        self.assertFalse(calls)

    def test_le_pdf_du_devis_recoit_les_pages_en_queue(self):
        if not _wkhtmltopdf_ok(self.env):
            self.skipTest("wkhtmltopdf absent")
        line = self._line(self.oak)
        report = self.env.ref("sale.action_report_saleorder").with_context(force_report_rendering=True)
        self.tmpl.drawing_template_id = False
        plain, _type = report._render_qweb_pdf(report.report_name, res_ids=line.order_id.ids)
        self.tmpl.drawing_template_id = self.drawing_template
        engine, _calls = self._engine()
        with engine:
            pdf, _type = report._render_qweb_pdf(report.report_name, res_ids=line.order_id.ids)
        base = PdfFileReader(io.BytesIO(plain), strict=False)
        reader = PdfFileReader(io.BytesIO(pdf), strict=False)
        # ⚠️ Deux pages de plan, pas trois : une page SVG de 297 mm ne déborde pas sur une page blanche.
        self.assertEqual(len(reader.pages), len(base.pages) + 2)
        portrait, landscape = reader.pages[-2], reader.pages[-1]
        # A4 en points : 595 × 842 ; la page paysage est couchée.
        self.assertAlmostEqual(float(portrait.mediabox.width), 595, delta=2)
        self.assertAlmostEqual(float(landscape.mediabox.width), 842, delta=2)

    def test_le_pdf_garde_l_echelle_exacte(self):
        """⚠️ 100 mm du dessin font 100 mm sur le papier, à leur place ([[L-573]]).

        ⓘ Mesuré sur la page RASTÉRISÉE à 10 points par mm : le trait du SVG va de x = 10 à 110 mm, à y = 20 mm.
        """
        if not _wkhtmltopdf_ok(self.env) or not shutil.which("pdftoppm"):
            self.skipTest("wkhtmltopdf ou pdftoppm absent")
        line = self._line(self.oak)
        report = self.env.ref("sale.action_report_saleorder").with_context(force_report_rendering=True)
        engine, _calls = self._engine()
        with engine:
            pdf, _type = report._render_qweb_pdf(report.report_name, res_ids=line.order_id.ids)
        count = len(PdfFileReader(io.BytesIO(pdf), strict=False).pages)
        start, length, row = _longest_dark_run(pdf, count - 1)
        self.assertAlmostEqual(length, 100.0, delta=0.5)
        self.assertAlmostEqual(start, 10.0, delta=0.5)
        self.assertAlmostEqual(row, 20.0, delta=0.5)


def _longest_dark_run(pdf, page, per_mm=10):
    """Le plus long trait horizontal sombre d'une page : `(début, longueur, rangée)` en mm."""
    with tempfile.TemporaryDirectory() as folder:
        source = f"{folder}/doc.pdf"
        with open(source, "wb") as f:
            f.write(pdf)
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(per_mm * 25.4), "-gray", "-png",
                        "-singlefile", source, f"{folder}/page"], check=True)
        image = Image.open(f"{folder}/page.png").convert("L")
        width, height = image.size
        pixels = image.load()
        best = (0, 0, 0)
        for y in range(height):
            run_start = None
            for x in range(width + 1):
                dark = x < width and pixels[x, y] < 128
                if dark and run_start is None:
                    run_start = x
                elif not dark and run_start is not None:
                    if x - run_start > best[1]:
                        best = (run_start, x - run_start, y)
                    run_start = None
    return best[0] / per_mm, best[1] / per_mm, best[2] / per_mm


@tagged("post_install", "-at_install")
class TestQuoteDrawingPortal(DrawingCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixture()

    def test_le_portail_montre_le_plan_sous_la_ligne(self):
        line = self._line(self.oak)
        order = line.order_id
        order._portal_ensure_token()
        engine, _calls = self._engine()
        with engine:
            response = self.url_open(f"/my/orders/{order.id}?access_token={order.access_token}")
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("o_drawing_portal_row", html)
        self.assertEqual(html.count('class="o_drawing_portal_page'), 2)
        self.assertIn('width="297mm"', html)
