# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Les trois réglages d'une LIGNE, visibles là où l'on travaille — 2026-09-07.

Gerry : *« dans la fiche produit, dans la partie attribut, je vois que l'on ne
peut pas modifier en ligne Required, Multi et Allow add — est-ce normal ? »*

⚠️ **Les colonnes existaient**, mais conditionnées au contexte du menu
« Produits configurables » (`default_config_ok`). Sur la fiche produit
ordinaire — celle qu'on ouvre pour éditer une pièce — elles étaient donc
invisibles, alors que ces trois drapeaux sont **lus à l'exécution** :
`answer_field` lit `custom` pour choisir entre une liste et une saisie, et la
page du configurateur lit `multi` pour accumuler les réponses.

ⓘ C'est le même défaut que `default_val` avait déjà payé (2026-09-02), et pour
la même raison : une pièce peut porter un modèle 3D **sans** être configurable.
"""
from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class LineFlagColumns(TransactionCase):

    def _colonnes(self, contexte=None):
        """Les colonnes de la liste des lignes d'attribut, telles que RENDUES."""
        arch = self.env["product.template"].with_context(**(contexte or {})).get_view(
            self.env.ref("product.product_template_only_form_view").id, "form"
        )["arch"]
        return {
            champ.get("name"): champ
            for champ in etree.fromstring(arch).xpath(
                "//field[@name='attribute_line_ids']/list/field"
            )
        }

    def test_les_trois_reglages_sont_DANS_la_liste(self):
        colonnes = self._colonnes()
        for nom in ("required", "multi", "custom"):
            self.assertIn(nom, colonnes, "« %s » manque à la liste" % nom)

    def test_ils_se_voient_SANS_le_contexte_du_menu_configurable(self):
        """⚠️ Le cœur du relevé : la fiche produit ordinaire n'a pas ce contexte."""
        colonnes = self._colonnes()
        for nom in ("required", "multi", "custom"):
            with self.subTest(champ=nom):
                self.assertNotIn(
                    "default_config_ok", colonnes[nom].get("column_invisible", ""),
                    "« %s » se cache hors du menu des produits configurables" % nom,
                )

    def test_ils_se_voient_AUSSI_dans_ce_menu(self):
        colonnes = self._colonnes({"default_config_ok": True})
        for nom in ("required", "multi", "custom"):
            self.assertIn(nom, colonnes)

    def test_le_libelle_d_ajout_reste_celui_que_Gerry_a_choisi(self):
        """« Custom » ne disait rien ; le drapeau autorise l'AJOUT d'une valeur."""
        self.assertEqual(self._colonnes()["custom"].get("string"), "Allow add")

    def test_ils_restent_MODIFIABLES(self):
        """Une colonne en lecture seule n'aurait rien réglé : c'est « modifier en
        ligne » qui était demandé."""
        colonnes = self._colonnes()
        for nom in ("required", "multi", "custom"):
            with self.subTest(champ=nom):
                self.assertNotEqual(colonnes[nom].get("readonly"), "1")


@tagged("post_install", "-at_install")
class KanbanConfigureIcon(TransactionCase):
    """L'icône « configurer » d'une vignette de produit — Gerry, 2026-09-07.

    *« Dans la card du kanban, remplace la clé par l'icône du crayon et ajoute
    une marge à droite avant l'étoile. »*

    ⓘ Le crayon est celui qu'Odoo emploie déjà pour ce geste — le bouton de la
    cellule produit d'une ligne de devis en porte un. Deux dessins pour un même
    geste font hésiter.
    """

    def _icone(self):
        arch = self.env["product.template"].get_view(
            self.env.ref("product.product_template_kanban_view").id, "kanban"
        )["arch"]
        noeuds = etree.fromstring(arch).xpath(
            "//a[@name='configure_product']/i"
        )
        self.assertTrue(noeuds, "l'icône de configuration a disparu de la vignette")
        return noeuds[0]

    def test_c_est_un_CRAYON(self):
        self.assertIn("fa-pencil", self._icone().get("class"))

    def test_ce_n_est_plus_une_CLÉ(self):
        self.assertNotIn("fa-wrench", self._icone().get("class"))

    def test_une_marge_le_sépare_de_l_ÉTOILE(self):
        """⚠️ Sans elle, deux gestes voisins se frôlent — et se cliquent l'un
        pour l'autre."""
        arch = self.env["product.template"].get_view(
            self.env.ref("product.product_template_kanban_view").id, "kanban"
        )["arch"]
        bloc = etree.fromstring(arch).xpath(
            "//a[@name='configure_product']/parent::div"
        )[0]
        self.assertIn("me-2", bloc.get("class"))
