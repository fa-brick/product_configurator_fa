"""LES FEUILLES DE STYLE DE CE MODULE COMPILENT-ELLES sous le compilateur d'ODOO ?

Odoo compile le SCSS avec **libsass**, qui refuse ce que le reste du monde accepte — le
`min()` de CSS, l'arithmétique à unités mêlées — et quand il refuse, c'est le BUNDLE ENTIER
qui tombe : la page revient à un style périmé, bandeau rouge compris ([[L-302]],
[[L-353]]). Ce banc ne raisonne pas : il COMPILE, comme le fait son pendant dans
`product_editor` (`test_scss_compiles.py`).

Arrivé avec la rangée qui défile (D-382), la première feuille du module à porter des
`calc()`.

⚠️ Le préambule remplace les variables qu'apporte le bundle d'Odoo par des valeurs du bon
TYPE. Une variable employée sans y figurer fait échouer le test sur « undefined
variable » : le message dit quoi ajouter.
"""
import pathlib

from odoo.tests import TransactionCase, tagged

try:
    import sass
except ImportError:  # pragma: no cover — libsass est une dépendance d'Odoo
    sass = None

PREAMBULE = "$o-brand-primary: #71639e;\n"
SRC = pathlib.Path(__file__).resolve().parent.parent / "static" / "src"


@tagged("post_install", "-at_install")
class TestScssCompiles(TransactionCase):

    def test_chaque_feuille_compile(self):
        if sass is None:
            self.skipTest("libsass absent")
        sheets = sorted(SRC.rglob("*.scss"))
        self.assertTrue(sheets)
        for sheet in sheets:
            with self.subTest(sheet=sheet.name):
                sass.compile(string=PREAMBULE + sheet.read_text(encoding="utf-8"))

    def test_le_banc_leve_sur_une_faute_connue(self):
        """⚠️ Le contrôle du contrôle : un banc qui ne sait pas échouer ne garde rien."""
        if sass is None:
            self.skipTest("libsass absent")
        with self.assertRaises(sass.CompileError):
            sass.compile(string=".x { width: min(100%, 15rem); }")
