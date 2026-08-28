"""Ce que chaque onglet montre — B3, D-209, D-210.

⚠️ *« L'onglet attribut et variant ne devait pas changer. »* Correction de Gerry
(2026-08-28) : j'avais lu Q2 — *« un seul ordre, partagé »* — comme *« les mêmes
colonnes »*. Partager l'ORDRE n'est pas partager l'AFFICHAGE.
"""

import re

from odoo.addons.base.tests.common import BaseCommon


class ConfiguratorColumns(BaseCommon):
    def _core_columns(self):
        """Les colonnes d'« Attributs & Variantes » — celle du cœur, intacte."""
        arch = self.env["product.template"].get_view(view_type="form")["arch"]
        for match in re.finditer(r'<field name="attribute_line_ids"', arch):
            bout = arch[match.start():]
            if "<list" not in bout:
                continue
            liste = bout[bout.index("<list"): bout.index("</list>")]
            return {
                m.group(1)
                for m in re.finditer(r'<(?:field|button) name="([a-z_0-9]+)"', liste)
            }
        self.fail("la liste d'Attributs & Variantes est introuvable")

    def test_01_the_ATTRIBUTES_tab_is_left_alone(self):
        """⚠️ Ce qui appartient au configurateur ne revient pas ici.

        ⓘ La garde ne fige pas la liste du cœur — le fork y ajoutait déjà ses
        propres colonnes avant ce chantier. Elle interdit d'y reverser CELLES du
        configurateur.
        """
        du_configurateur = {
            "visibility_domain_id", "visibility_domain_summary",
            "config_step_id", "config_step_owner_id",
            "view_camera_id", "action_open_values", "too_many_values",
        }
        intrus = du_configurateur & self._core_columns()
        self.assertEqual(
            intrus, set(),
            f"des colonnes du configurateur sont revenues dans l'onglet : {intrus}",
        )

    def test_02_the_configurator_tab_holds_the_TREE(self):
        """⚠️ Et il ne le déclare qu'UNE FOIS.

        Un même `One2many` déclaré deux fois dans un formulaire casse la
        sauvegarde (D-209, mesuré) : la garde compte les occurrences autant
        qu'elle vérifie la présence.
        """
        arch = self.env["product.template"].get_view(view_type="form")["arch"]
        occurrences = re.findall(r'<field name="configurator_line_ids"[^>]*', arch)
        self.assertEqual(len(occurrences), 1, "le champ de l'arbre est déclaré deux fois")
        self.assertIn('widget="configurator_tree"', occurrences[0])
