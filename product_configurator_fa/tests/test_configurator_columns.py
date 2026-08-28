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

    def _core_list(self):
        """La liste d'« Attributs & Variantes », telle qu'elle est assemblée."""
        arch = self.env["product.template"].get_view(view_type="form")["arch"]
        for match in re.finditer(r'<field name="attribute_line_ids"', arch):
            bout = arch[match.start():]
            if "<list" not in bout:
                continue
            return bout[bout.index("<list"): bout.index("</list>")]
        self.fail("la liste d'Attributs & Variantes est introuvable")

    def test_03_the_columns_say_what_they_DO(self):
        """⚠️ « Custom » ne disait rien, et « Default Val » était tronqué.

        Constat de Gerry : *« Custom n'a plus d'intérêt, c'est allow add »*. Le
        drapeau autorise le client à AJOUTER une valeur — et cette saisie crée
        une vraie valeur d'attribut (D-081), elle ne reste pas éphémère.
        """
        liste = self._core_list()
        self.assertIn('string="Allow add"', liste)
        self.assertIn('string="Default value"', liste)

    def test_04_and_VALEURS_is_the_column_that_stretches(self):
        """⚠️ Sans largeur déclarée, la liste répartit la place à parts égales.

        Résultat constaté à l'écran : un grand vide au milieu, et la colonne des
        valeurs — la seule qui grandit avec le contenu — serrée comme les autres.
        On fixe donc celles de fin ; « Valeurs » prend le reste.
        """
        liste = self._core_list()
        # Chaque colonne de fin porte une largeur…
        for nom in ("default_val", "required", "multi", "custom"):
            bloc = re.search(
                r'<field\s+name="%s"[^>]*' % nom, liste, re.S
            )
            self.assertTrue(bloc, f"la colonne {nom} a disparu")
            self.assertIn("width=", bloc.group(0), f"{nom} n'a pas de largeur")
        # …et celle des valeurs, non : c'est elle qui s'étire.
        valeurs = re.search(r'<field\s+name="value_ids"[^>]*', liste, re.S)
        self.assertTrue(valeurs)
        self.assertNotIn("width=", valeurs.group(0))


class AttributePageLayout(BaseCommon):
    """L'agencement de la page d'attribut — maquette de Gerry (D-216).

    ⚠️ *« Insère toutes les informations dans informations générales. »* La page
    cesse d'être une pile de blocs de même rang : le titre et les trois drapeaux
    en tête, tout le reste dans un onglet.
    """

    def _arch(self):
        return self.env["product.attribute"].get_view(view_type="form")["arch"]

    def test_01_the_NAME_opens_the_page(self):
        """ⓘ Il était un champ parmi d'autres ; il ouvre désormais la page."""
        self.assertIn('class="oe_title"', self._arch())

    def test_02_the_three_flags_are_ABOVE_the_notebook(self):
        """⚠️ Ce sont les réglages qu'on veut voir en ouvrant un attribut.

        ⓘ Et leurs libellés perdent le préfixe « Default: » : le titre du bloc
        le dit maintenant, le répéter quatre fois alourdissait sans rien
        apprendre.
        """
        arch = self._arch()
        defauts = arch.index("Defaults for a new product line")
        carnet = arch.index("<notebook")
        self.assertLess(defauts, carnet, "les défauts sont passés sous le carnet")

    def test_03_everything_else_is_in_GENERAL_INFORMATION(self):
        """La maquette ne montre rien entre le titre et les défauts."""
        arch = self._arch()
        debut = arch.index('name="general_information"')
        fin = arch.index("</page>", debut)
        page = arch[debut:fin]
        for champ in ("display_type", "create_variant", "active",
                      "description", "value_type", "search_ok"):
            self.assertIn(f'name="{champ}"', page, f"{champ} n'est pas dans l'onglet")

    def test_04_and_it_comes_BEFORE_the_values(self):
        """⚠️ On lit ce qu'un attribut EST avant d'énumérer ce qu'il propose."""
        arch = self._arch()
        self.assertLess(
            arch.index('name="general_information"'),
            arch.index('name="attribute_values"'),
        )
