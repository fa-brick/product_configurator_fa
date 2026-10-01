# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""La fiche boutique d'un produit configurable ne repose pas ses QUESTIONS — W-69.

Arbitrage de Gerry (2026-10-01) : aucun sélecteur ; dans le tableau d'informations, seuls
les attributs « sans variante » à valeur unique (une information, pas un choix) ; le bouton
« Comparer » reste.
"""
import re

from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged


def _attribute(env, name, create_variant, *values):
    attribute = env["product.attribute"].create({"name": name, "create_variant": create_variant})
    return attribute, env["product.attribute.value"].create(
        [{"name": v, "attribute_id": attribute.id} for v in values])


def _shows(html, text):
    """Le texte est-il AFFICHÉ — entre deux balises ?

    ⚠️ Pas une simple recherche : Odoo dépose la table des exclusions de TOUTES les valeurs,
    en JSON, sur une `<ul>` vide que le panier lit (`data-attribute_exclusions`). Le nom d'une
    valeur y figure même quand aucun sélecteur n'est rendu (relevé le 2026-10-01).
    """
    return re.search(r">\s*" + re.escape(text) + r"\s*<", html) is not None


def _line(attribute, values, **extra):
    return Command.create({"attribute_id": attribute.id,
                           "value_ids": [Command.set(values.ids)], **extra})


class SingleValueTable(TransactionCase):
    """La règle, à la source : `_prepare_single_value_for_display`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.range_attr, cls.range_val = _attribute(env, "Gamme Zeta", "dynamic", "Pro Zeta")
        cls.wood_attr, cls.wood_val = _attribute(env, "Matiere Kappa", "no_variant", "Chene Kappa")
        cls.configurable = env["product.template"].create({
            "name": "Portail configurable", "config_ok": True,
            "attribute_line_ids": [_line(cls.range_attr, cls.range_val),
                                   _line(cls.wood_attr, cls.wood_val)],
        })
        cls.ordinary = env["product.template"].create({
            "name": "Portail ordinaire",
            "attribute_line_ids": [_line(cls.range_attr, cls.range_val),
                                   _line(cls.wood_attr, cls.wood_val)],
        })

    def _shown(self, tmpl):
        return list(tmpl.valid_product_template_attribute_line_ids
                    ._prepare_single_value_for_display())

    def test_01_un_produit_configurable_ne_garde_que_l_information(self):
        self.assertEqual(self._shown(self.configurable), [self.wood_attr])

    def test_02_un_produit_ordinaire_ne_change_pas(self):
        self.assertEqual(self._shown(self.ordinary), [self.range_attr, self.wood_attr])

    def test_03_un_recordset_qui_mele_les_deux_filtre_PAR_LIGNE(self):
        lines = (self.configurable | self.ordinary).valid_product_template_attribute_line_ids
        shown = lines._prepare_single_value_for_display()
        self.assertEqual(shown[self.range_attr].product_tmpl_id, self.ordinary)
        self.assertEqual(shown[self.wood_attr].product_tmpl_id, self.configurable | self.ordinary)


@tagged("post_install", "-at_install")
class ShopPageAttributes(HttpCase):
    """Ce que la fiche SERVIE montre — le rendu, pas seulement la méthode.

    ⚠️ **Deux produits configurables, et c'est un constat du 2026-10-01.** Un produit qui
    porte un attribut « sans variante » ne rend PAS le formulaire de sa fiche (ni prix, ni
    sélecteurs) une fois configuré : le chemin d'OCA met cette réponse DANS la variante, et
    Odoo, qui cherche la variante SANS elle, juge la combinaison impossible — la même cause
    que le défaut Q7 (`test_no_variant_answer.py`). Le premier produit éprouve donc les
    sélecteurs et le prix, le second le tableau d'informations.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.range_attr, cls.range_val = _attribute(env, "Gamme Zeta", "always", "Pro Zeta")
        cls.wood_attr, cls.wood_val = _attribute(env, "Matiere Kappa", "no_variant", "Chene Kappa")
        cls.color_attr, cls.colors = _attribute(env, "Teinte Omega", "always", "Rouge Omega", "Vert Omega")
        cls.configurable = env["product.template"].create({
            "name": "Portail configurable", "config_ok": True, "list_price": 100.0,
            "is_published": True,
            "attribute_line_ids": [_line(cls.range_attr, cls.range_val),
                                   _line(cls.color_attr, cls.colors)],
        })
        cls.informed = env["product.template"].create({
            "name": "Portail en chene", "config_ok": True, "list_price": 100.0,
            "is_published": True,
            "attribute_line_ids": [_line(cls.range_attr, cls.range_val),
                                   _line(cls.wood_attr, cls.wood_val),
                                   _line(cls.color_attr, cls.colors)],
        })
        cls.ordinary = env["product.template"].create({
            "name": "Portail ordinaire", "list_price": 50.0, "is_published": True,
            "attribute_line_ids": [_line(cls.range_attr, cls.range_val),
                                   _line(cls.color_attr, cls.colors)],
        })
        # ⚠️ **UNE CONFIGURATION CONFIRMÉE, sinon le test ne prouve rien.** Sans variante,
        # Odoo ne rend pas du tout le formulaire de la fiche — ni prix, ni sélecteurs : un
        # sélecteur absent n'y dirait rien de nos règles. Le JeNo, lui, a des variantes
        # (chaque configuration confirmée en fait naître une) : c'est ce cas qu'on éprouve.
        env["product.config.session"].create({
            "product_tmpl_id": cls.configurable.id, "user_id": env.user.id,
            "value_ids": [Command.set((cls.range_val | cls.colors[0]).ids)],
        }).create_get_variant()

    def test_00_la_fiche_rend_bien_son_formulaire(self):
        """Le témoin : le prix d'Odoo est là — les absences ci-dessous ont donc un sens."""
        html = self.url_open(self.configurable.website_url).text
        self.assertIn("product_price", html)

    def test_01_pas_de_selecteur_la_question_se_pose_au_configurateur(self):
        html = self.url_open(self.configurable.website_url).text
        self.assertNotIn("variant_attribute", html)     # aucun sélecteur rendu
        self.assertFalse(_shows(html, "Rouge Omega"))
        self.assertFalse(_shows(html, "Vert Omega"))

    def test_02_le_prix_s_annonce_comme_un_plancher(self):
        html = self.url_open(self.configurable.website_url).text
        self.assertIn("o_cfg3d_from", html)

    def test_03_le_tableau_garde_l_information_pas_la_question(self):
        html = self.url_open(self.informed.website_url).text
        self.assertTrue(_shows(html, "Chene Kappa"))    # « sans variante » à valeur unique : reste
        self.assertFalse(_shows(html, "Pro Zeta"))      # question à valeur unique : partie

    def test_04_un_produit_ordinaire_garde_ses_selecteurs_et_son_tableau(self):
        html = self.url_open(self.ordinary.website_url).text
        # Sélecteurs, ou liste des variantes si la boutique est réglée ainsi (fabk18) : le
        # choix est offert dans les deux cas.
        self.assertTrue("variant_attribute" in html or "radio_variant_" in html)
        self.assertTrue(_shows(html, "Pro Zeta"))
        self.assertNotIn("o_cfg3d_from", html)

    def test_05_pas_de_liste_des_configurations_passees(self):
        """⚠️ Le mode « Liste des variantes » remplace les sélecteurs par UN BOUTON PAR VARIANTE :
        pour un produit configurable, les configurations des autres clients, à l'achat."""
        self.env.ref("website_sale.product_variants").active = True
        self.env["product.config.session"].create({
            "product_tmpl_id": self.configurable.id, "user_id": self.env.user.id,
            "value_ids": [Command.set((self.range_val | self.colors[1]).ids)],
        }).create_get_variant()
        self.assertGreater(self.configurable.product_variant_count, 1)
        html = self.url_open(self.configurable.website_url).text
        self.assertNotIn("radio_variant_", html)
        ordinary = self.url_open(self.ordinary.website_url).text
        self.assertIn("radio_variant_", ordinary)            # le mode est bien actif

