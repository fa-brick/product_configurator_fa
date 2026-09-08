# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""COMPARER une réponse à un NOMBRE — `épaisseur > 4`.

Demande de Gerry (2026-09-07) : *« il faut tenir compte des opérateurs supérieur
inférieur et égalité pour le configurateur l'éditeur »*.

⚠️ **UNE COMPARAISON N'EST PAS UNE APPARTENANCE.** Les conditions d'OCA testent des
valeurs CHOISIES : `montage in [ressort avant, ressort arrière]`. Une question numérique
ne se répond pas en choisissant — sa réponse est SAISIE, et vit dans `custom_vals`. Les
deux formes cohabitent donc dans le même stockage, distinguées par le champ qu'elles
remplissent : `value_ids` d'un côté, `numeric_value` de l'autre.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestNumericCondition(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.epaisseur = cls.env["product.attribute"].create({
            "name": "Épaisseur", "create_variant": "no_variant",
            "custom_type": "float",
        })
        cls.couleur = cls.env["product.attribute"].create({
            "name": "Couleur", "create_variant": "no_variant",
        })
        cls.rouge = cls.env["product.attribute.value"].create(
            {"name": "Rouge", "attribute_id": cls.couleur.id})
        cls.domaine = cls.env["product.config.domain"].create({"name": "Épaisse"})
        cls.regle = cls.env["product.config.domain.line"].create({
            "domain_id": cls.domaine.id,
            "attribute_id": cls.epaisseur.id,
            "condition": ">",
            "numeric_value": 4.0,
            "operator": "and",
        })

    # ── LE STOCKAGE ──────────────────────────────────────────────────────

    def test_une_comparaison_ne_porte_PAS_de_valeurs(self):
        """Les deux formes se distinguent par le champ qu'elles remplissent : les
        mêler donnerait une règle qu'aucun évaluateur ne sait lire."""
        with self.assertRaises(ValidationError):
            self.regle.value_ids = [(6, 0, [self.rouge.id])]

    def test_une_comparaison_exige_une_question_NUMÉRIQUE(self):
        """Sur une question de couleur, `> 4` serait stockée puis évaluée contre une
        réponse qui n'est pas un nombre : fausse, toujours, et en silence."""
        with self.assertRaises(ValidationError):
            self.env["product.config.domain.line"].create({
                "domain_id": self.domaine.id,
                "attribute_id": self.couleur.id,
                "condition": ">=",
                "numeric_value": 2.0,
                "operator": "and",
            })

    # ── L'ALLER-RETOUR VERS L'ÉDITEUR ────────────────────────────────────

    def test_la_regle_part_vers_l_editeur_avec_son_NOMBRE(self):
        champ = self.domaine._attribute_field_name(self.epaisseur)
        self.assertEqual(self.domaine.to_odoo_domain(), [(champ, ">", 4.0)])

    def test_un_domaine_SAISI_redevient_une_regle_numerique(self):
        champ = self.domaine._attribute_field_name(self.epaisseur)
        self.domaine.from_odoo_domain([(champ, "<=", 12.5)])
        ligne = self.domaine.domain_line_ids
        self.assertEqual(len(ligne), 1)
        self.assertEqual(ligne.condition, "<=")
        self.assertEqual(ligne.numeric_value, 12.5)
        self.assertFalse(ligne.value_ids)

    def test_un_EGAL_sur_une_question_a_valeurs_reste_une_appartenance(self):
        """⚠️ `=` veut dire deux choses, et c'est la QUESTION qui tranche. Le sélecteur
        écrit `('champ', '=', id)` pour désigner une valeur : le lire comme un nombre
        stockerait l'identifiant de « Rouge » comme une mesure."""
        champ = self.domaine._attribute_field_name(self.couleur)
        self.domaine.from_odoo_domain([(champ, "=", self.rouge.id)])
        ligne = self.domaine.domain_line_ids
        self.assertEqual(ligne.condition, "in")
        self.assertEqual(ligne.value_ids, self.rouge)

    # ── L'ÉVALUATION ─────────────────────────────────────────────────────

    def _verdict(self, reponse):
        """La condition, évaluée contre une réponse saisie."""
        session = self.env["product.config.session"]
        return session.validate_domains_against_sels(
            self.domaine.compute_domain(), value_ids=[],
            custom_vals={self.epaisseur.id: reponse})

    def test_la_comparaison_tranche_dans_les_deux_sens(self):
        self.assertTrue(self._verdict(6.0))
        self.assertFalse(self._verdict(2.0))
        self.assertFalse(self._verdict(4.0))          # `>` est strict

    def test_une_reponse_ABSENTE_ne_satisfait_pas_la_regle(self):
        """⚠️ C'est l'INVERSE de la doctrine de l'éditeur 3D (D-150, « on ignore ce
        qu'on ne sait pas »), et c'est voulu : ici la condition gouverne ce qu'on
        PROPOSE au client. Proposer sur la foi d'une réponse manquante ouvrirait des
        questions que la règle voulait fermer."""
        self.assertFalse(self._verdict(None))
        self.assertFalse(self._verdict("deux"))

    # ── CE QUE L'ŒIL EN LIT ──────────────────────────────────────────────

    def test_la_pastille_se_lit_comme_elle_s_ecrit(self):
        self.assertEqual(self.domaine.condition_summary, "Épaisseur > 4")
