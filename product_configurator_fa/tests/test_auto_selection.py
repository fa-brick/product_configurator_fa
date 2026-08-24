# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Une valeur seule disponible se retient d'elle-même — D-167.

La règle ferme deux points d'un coup : l'attribut **dérivé** (restreindre à une
seule valeur vaut la poser, et la cascade « laquage spécial → couleur profil ∈
{blanc} » n'a plus besoin d'un moteur de règles) et la **teinte que l'enfant n'a
pas** (D-166), où la valeur sans condition reste seule et devient le repli.

⚠️ Ce qui est éprouvé ici est autant le périmètre que la règle : imposer l'unique
valeur d'une liste à cocher, ou d'une question facultative, transformerait une
option en obligation. Le refus est aussi un comportement.
"""
from odoo import Command
from odoo.tests import TransactionCase


class AutoSelectSingleValue(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.wizard = cls.env["product.configurator"]

        cls.attr_finish = Attribute.create({"name": "Finition"})
        cls.finish_standard, cls.finish_special = Value.create([
            {"name": "Teinte de stock", "attribute_id": cls.attr_finish.id},
            {"name": "Laquage spécial", "attribute_id": cls.attr_finish.id},
        ])
        cls.attr_color = Attribute.create({"name": "Couleur profil"})
        cls.color_white, cls.color_black = Value.create([
            {"name": "Blanc", "attribute_id": cls.attr_color.id},
            {"name": "Noir", "attribute_id": cls.attr_color.id},
        ])

        cls.tmpl = cls.env["product.template"].create({
            "name": "Profil configurable",
            "config_ok": True,
            "attribute_line_ids": [
                Command.create({
                    "attribute_id": cls.attr_finish.id,
                    "value_ids": [Command.set(
                        (cls.finish_standard | cls.finish_special).ids)],
                    "required": True,
                }),
                Command.create({
                    "attribute_id": cls.attr_color.id,
                    "value_ids": [Command.set(
                        (cls.color_white | cls.color_black).ids)],
                    "required": True,
                }),
            ],
        })
        cls.color_line = cls.tmpl.attribute_line_ids.filtered(
            lambda line: line.attribute_id == cls.attr_color
        )
        # ⚠️ Une règle OCA dit « ces valeurs-ci ne sont offertes QUE si… » ; elle
        # n'écarte pas les autres. Pour ne laisser que le blanc en laquage spécial,
        # c'est donc le NOIR qu'il faut restreindre — un profil noir n'existe qu'en
        # teinte de stock. Le blanc, lui, reste offert en toutes circonstances : il
        # est la valeur sans condition, le FILET de D-167.
        domain_stock = cls.env["product.config.domain"].create({
            "name": "Finition = teinte de stock",
            "domain_line_ids": [Command.create({
                "attribute_id": cls.attr_finish.id,
                "condition": "in",
                "value_ids": [Command.set(cls.finish_standard.ids)],
            })],
        })
        cls.env["product.config.line"].create({
            "product_tmpl_id": cls.tmpl.id,
            "attribute_line_id": cls.color_line.id,
            "value_ids": [Command.set(cls.color_black.ids)],
            "domain_id": domain_stock.id,
        })
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": cls.tmpl.id,
            "user_id": cls.env.user.id,
        })

    def _field(self, attribute):
        return self.wizard._prefixes.get("field_prefix") + str(attribute.id)

    def _form_vals(self, chosen, answered=None):
        """Les valeurs que l'assistant renverrait pour une configuration donnée."""
        domains = self.wizard.get_onchange_domains(
            chosen.ids, self.tmpl, self.session,
        )
        dynamic = {self._field(self.attr_finish): chosen[:1].id}
        dynamic[self._field(self.attr_color)] = answered.id if answered else False
        return self.wizard.get_form_vals(
            dynamic, domains,
            product_tmpl_id=self.tmpl, config_session_id=self.session,
        ), domains

    def test_la_seule_valeur_restante_se_retient_d_elle_meme(self):
        vals, domains = self._form_vals(self.finish_special)
        # La règle a bien réduit la liste à une seule teinte…
        self.assertEqual(domains[self._field(self.attr_color)][0][2],
                         self.color_white.ids)
        # … et c'est elle qui est retenue, sans que le client ait à cliquer.
        self.assertEqual(vals[self._field(self.attr_color)], self.color_white.id)

    def test_deux_valeurs_possibles_ne_decident_de_RIEN(self):
        """⚠️ La règle vaut pour « la seule solution », jamais pour « la
        première » : choisir à la place du client serait un défaut, pas un
        confort."""
        vals, _domains = self._form_vals(self.finish_standard)
        self.assertFalse(vals.get(self._field(self.attr_color)))

    def test_une_reponse_devenue_indisponible_est_REMPLACÉE(self):
        """L'autre moitié existait déjà — l'assistant sait EFFACER. Les deux vont
        ensemble et dans cet ordre, sinon la valeur effacée resterait vide."""
        vals, _domains = self._form_vals(self.finish_special,
                                         answered=self.color_black)
        self.assertEqual(vals[self._field(self.attr_color)], self.color_white.id)

    def test_une_reponse_encore_valable_n_est_pas_touchee(self):
        vals, _domains = self._form_vals(self.finish_special,
                                         answered=self.color_white)
        self.assertEqual(vals[self._field(self.attr_color)], self.color_white.id)

    def test_une_question_FACULTATIVE_reste_vide(self):
        """⚠️ Périmètre assumé : la remplir d'office la rendrait impossible à
        laisser vide, puisque chaque onchange la reposerait. Les cas du terrain
        sont tous obligatoires (D-165, Q-7)."""
        self.color_line.required = False
        vals, _domains = self._form_vals(self.finish_special)
        self.assertFalse(vals.get(self._field(self.attr_color)))

    def test_une_liste_a_COCHER_reste_vide(self):
        """Imposer l'unique valeur d'un `multi` transformerait une option en
        obligation."""
        self.color_line.multi = True
        vals, _domains = self._form_vals(self.finish_special)
        self.assertFalse(vals.get(self._field(self.attr_color)))
