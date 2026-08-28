"""Ce que la liste unifiée montre — B3.

⚠️ Ces gardes lisent la vue ASSEMBLÉE, pas le fichier XML : une colonne peut être
déclarée et n'apparaître nulle part si un `xpath` d'un autre module la déplace,
ou si le champ manque au modèle. C'est la même couture que pour les prix (D-197).
"""

import re

from odoo.addons.base.tests.common import BaseCommon


class ConfiguratorColumns(BaseCommon):
    def _columns(self):
        """Les colonnes de la liste de l'ONGLET CONFIGURATEUR, avec leur masquage.

        ⚠️ **Il y a DEUX listes de `attribute_line_ids` dans la fiche produit**, et
        elles ne doivent pas se ressembler : celle d'« Attributs & Variantes »,
        qui ne change pas, et celle du configurateur. Viser la première par sa
        position ferait mesurer la mauvaise — c'est exactement l'erreur que Gerry
        a relevée le 2026-08-28. On reconnaît donc la bonne à ce qu'elle SEULE
        porte : la colonne de condition.

        ⚠️ Et le découpage vise la BALISE, pas le nom : `name="attribute_line_ids"`
        apparaît aussi dans des `depends` bien plus haut dans la fiche.
        """
        arch = self.env["product.template"].get_view(view_type="form")["arch"]
        for match in re.finditer(r'<field name="configurator_line_ids"', arch):
            bout = arch[match.start():]
            if "<list" not in bout:
                continue
            liste = bout[bout.index("<list"): bout.index("</list>")]
            if 'name="visibility_domain_id"' not in liste:
                continue
            colonnes = {}
            for champ in re.finditer(r'<(?:field|button) name="([a-z_0-9]+)"([^>]*)', liste):
                garde = re.search(r'column_invisible="([^"]*)"', champ.group(2))
                colonnes[champ.group(1)] = garde.group(1) if garde else "False"
            return colonnes
        self.fail("la liste de l'onglet configurateur est introuvable")

    def _core_columns(self):
        """Les colonnes de la liste d'« Attributs & Variantes » — celle du cœur."""
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
        # ⓘ Aucune garde de contexte n'est nécessaire : c'est l'onglet ENTIER
        # qui est masqué hors d'un produit configurable (`invisible="not
        # config_ok"`). Exiger `default_config_ok` ici serait exiger une ceinture
        # par-dessus des bretelles — et faire échouer la garde sur du code juste.
        self.assertNotEqual(colonnes["visibility_domain_id"], "True")

    def test_02_and_it_carries_its_SUMMARY_so_the_facets_can_show(self):
        """⚠️ Sans le résumé déclaré, le widget n'aurait rien à afficher.

        Un widget posé sur un Many2one ne reçoit que l'identifiant et le nom de
        sa cible, jamais ses champs (D-203).
        """
        colonnes = self._columns()
        self.assertIn("visibility_domain_summary", colonnes)
        self.assertEqual(colonnes["visibility_domain_summary"], "True")

    def test_03_the_ATTRIBUTES_tab_is_left_alone(self):
        """⚠️ *« L'onglet attribut et variant ne devait pas changer. »*

        Correction de Gerry (2026-08-28). J'avais lu Q2 — *« un seul ordre,
        partagé »* — comme *« les mêmes colonnes »*. Partager l'ORDRE n'est pas
        partager l'AFFICHAGE : c'est le même `attribute_line_ids`, donc la même
        séquence, montré autrement.

        ⓘ Cette garde ne fige pas la liste du cœur — le fork y ajoutait déjà ses
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

    def test_04_and_the_configurator_list_carries_them_ALL(self):
        """Le pendant : ce qui a quitté l'onglet doit être arrivé quelque part."""
        colonnes = self._columns()
        # ⚠️ `view_camera_id` N'EST PAS ICI : il vient du PONT, chargé APRÈS ce
        # module. Une garde du cœur qui l'exigerait échouerait pendant sa propre
        # mise à jour — elle vit donc dans les tests du pont.
        for nom in ("visibility_domain_id", "config_step_id", "action_open_values"):
            self.assertIn(nom, colonnes)
