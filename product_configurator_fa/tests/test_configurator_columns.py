"""Ce que la liste unifiée montre — B3.

⚠️ Ces gardes lisent la vue ASSEMBLÉE, pas le fichier XML : une colonne peut être
déclarée et n'apparaître nulle part si un `xpath` d'un autre module la déplace,
ou si le champ manque au modèle. C'est la même couture que pour les prix (D-197).
"""

import re

from odoo.addons.base.tests.common import BaseCommon


class ConfiguratorColumns(BaseCommon):
    def _columns(self):
        """Les colonnes de la liste des lignes d'attribut, avec leur masquage.

        ⚠️ Le découpage doit viser la BALISE, pas le nom : `name="attribute_line_ids"`
        apparaît aussi dans des `depends` et des domaines bien plus haut dans la
        fiche produit. Coupé là, le test lisait quarante champs du formulaire et
        aurait pu passer sans que la liste porte quoi que ce soit.
        """
        arch = self.env["product.template"].get_view(view_type="form")["arch"]
        debut = arch.index('<field name="attribute_line_ids"')
        arch = arch[debut:]
        arch = arch[arch.index("<list"): arch.index("</list>")]
        colonnes = {}
        for match in re.finditer(r'<field name="([a-z_0-9]+)"([^>]*)', arch):
            garde = re.search(r'column_invisible="([^"]*)"', match.group(2))
            colonnes[match.group(1)] = garde.group(1) if garde else "False"
        return colonnes

    def test_01_the_CONDITION_reads_next_to_what_it_restricts(self):
        """Le gain de l'unification : la restriction cesse d'être ailleurs.

        Le champ existait sur la ligne d'attribut et ne se voyait que dans son
        formulaire — il fallait ouvrir chaque ligne pour savoir laquelle porte
        une condition.
        """
        colonnes = self._columns()
        self.assertIn("visibility_domain_id", colonnes)
        # ⚠️ PRÉSENTE NE VEUT PAS DIRE VISIBLE. Une colonne déclarée puis masquée
        # par `column_invisible="True"` passerait un test de simple présence — et
        # l'écran n'aurait rien. La garde exige donc que le seul masquage soit
        # celui du configurateur.
        self.assertIn("default_config_ok", colonnes["visibility_domain_id"])
        self.assertNotEqual(colonnes["visibility_domain_id"], "True")

    def test_02_and_it_carries_its_SUMMARY_so_the_facets_can_show(self):
        """⚠️ Sans le résumé déclaré, le widget n'aurait rien à afficher.

        Un widget posé sur un Many2one ne reçoit que l'identifiant et le nom de
        sa cible, jamais ses champs (D-203).
        """
        colonnes = self._columns()
        self.assertIn("visibility_domain_summary", colonnes)
        self.assertEqual(colonnes["visibility_domain_summary"], "True")

    def test_03_the_configurator_columns_stay_OUT_of_an_ordinary_product(self):
        """⚠️ Elles n'ont de sens que sur un produit configurable.

        Les afficher partout encombrerait la fiche de tous les autres produits
        d'un vocabulaire qui ne les concerne pas.
        """
        colonnes = self._columns()
        for nom in ("visibility_domain_id", "config_step_id", "required"):
            self.assertIn(
                "default_config_ok", colonnes[nom],
                f"la colonne {nom} s'affiche hors du configurateur",
            )
