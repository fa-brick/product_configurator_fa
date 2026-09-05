# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""L'état d'une session, tel que la PAGE PUBLIQUE le lit — D-091, lot 6.

Ce module ne sait rien du HTTP : il rend un dictionnaire. Le contrôleur ne fait
que l'appeler, ce qui rend l'essentiel éprouvable **sans serveur** — et c'est ce
qui manquait au lot 6, dont le blocage n° 4 était l'absence de tout harnais.

⚠️ **Ce que la page reçoit, et ce qu'elle ne reçoit PAS.** Elle reçoit les
questions, leurs réponses possibles, le prix et la définition 3D. Elle ne reçoit
ni identifiant interne de session, ni jeton d'une autre, ni rien qui permette
d'énumérer : le jeton entre, il ne ressort pas.
"""
from odoo import models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def _web_attribute_lines(self):
        """Les questions du produit, avec ce qui reste disponible.

        ⚠️ La disponibilité se demande à `values_available` — celle qui sert déjà
        à l'assistant — et non à une règle réécrite ici. Deux évaluateurs d'une
        même restriction finiraient par diverger, et c'est le client qui verrait
        la différence.
        """
        self.ensure_one()
        chosen = self.value_ids.ids
        out = []
        for line in self.product_tmpl_id.attribute_line_ids.sorted():
            values = line._configurator_value_ids()
            available = set(
                self.values_available(
                    check_val_ids=values.ids,
                    value_ids=chosen,
                    product_template_attribute_line_id=line.id,
                )
            )
            out.append({
                "id": line.attribute_id.id,
                "name": line.attribute_id.name,
                "required": bool(line.required),
                "multi": bool(line.multi),
                "values": [
                    {
                        "id": value.id,
                        "name": value.name,
                        # ⚠️ La valeur INDISPONIBLE est rendue quand même, marquée.
                        # C'est D-168 et D-178 : on la grise, et un appui dira
                        # pourquoi. La retirer ici ôterait à la page le moyen de
                        # le faire.
                        "available": value.id in available,
                        "chosen": value.id in chosen,
                    }
                    for value in values
                ],
            })
        return out

    def _web_model3d(self):
        """Le modèle 3D du produit configuré, ou rien."""
        self.ensure_one()
        # ⚠️ `_root_model3d` vient de l'ÉDITEUR (LGPL) ; ce module dépend des deux,
        # et c'est le seul endroit du dépôt qui en ait le droit (D-075).
        return self.product_tmpl_id._root_model3d()

    def _web_values(self):
        """`{attribut → valeur}` — la forme que le moteur 3D attend (D-163)."""
        self.ensure_one()
        return {value.attribute_id.id: value.id for value in self.value_ids}

    def _web_missing_attributes(self):
        """Les questions OBLIGATOIRES restées sans réponse.

        ⚠️ **La visibilité passe AVANT l'exigence** — c'est la règle de D-086 :
        un attribut masqué par une condition cesse d'être obligatoire. Sans
        cela, une question que le client ne voit pas l'empêcherait de terminer,
        et rien à l'écran ne dirait pourquoi.

        ⓘ On ne s'appuie PAS sur `check_and_open_incomplete_step` : elle ne
        regarde que les ÉTAPES (`get_open_step_lines`), donc un produit qui n'en
        déclare aucune passerait sans contrôle. La page ne montre pas encore les
        étapes ; elle doit pourtant refuser une configuration incomplète.
        """
        self.ensure_one()
        chosen = self.value_ids
        missing = self.env["product.template.attribute.line"]
        for line in self.product_tmpl_id.attribute_line_ids:
            if not line.required or not line._is_visible(value_ids=chosen):
                continue
            if not (line._configurator_value_ids() & chosen):
                missing |= line
        return missing

    def _web_after_confirm(self):
        """Ce qui suit la confirmation, là où la configuration ATTERRIT.

        Vide ici, et c'est voulu : le cœur de l'interface ne sait pas ce qu'est
        un devis. `product_configurator_web_3d_sale` s'y branche pour écrire la
        ligne. Un autre atterrissage (un panier, une demande) s'y brancherait
        pareil, sans toucher à cette classe.
        """
        return True

    def web_confirm(self):
        """Terminer la configuration : la variante naît, la session se ferme.

        ⚠️ **Une session confirmée ne se rouvre pas.** Elle a donné sa variante,
        et cette variante peut déjà être sur une commande : la changer ensuite
        serait pire qu'un refus (D-190, même raison que `set_value`).
        """
        self.ensure_one()
        missing = self._web_missing_attributes()
        if missing:
            # ⓘ Les NOMS, pas seulement le refus : la page doit pouvoir dire ce
            # qui manque, et l'utilisateur ne connaît pas nos identifiants.
            return {
                "error": "incomplete",
                "missing": missing.attribute_id.mapped("name"),
            }
        self.action_confirm()
        self._web_after_confirm()
        return self.web_state()

    def action_open_3d_page(self):
        """L'action qui EMMÈNE à la page 3D de cette configuration.

        Un seul endroit fabrique cette URL : la fiche produit et la ligne de
        devis y passent toutes les deux. Le jeton reste la seule identité, même
        au back-office — c'est ce qui permet d'ouvrir la même page, pour un
        interne comme pour un client (D-091).

        ⓘ `target: "new"` — un onglet à côté, et non à la place : le commercial
        garde son devis ouvert derrière.
        """
        self.ensure_one()
        self._ensure_access_token()
        return {
            "type": "ir.actions.act_url",
            "url": f"/configurator/{self.access_token}",
            "target": "new",
        }

    def web_state(self):
        """Tout ce qu'il faut à la page, en UNE réponse.

        ⚠️ Un seul aller-retour : la page s'ouvre sur un lien reçu par courriel,
        souvent sur un téléphone, et trois requêtes en série coûteraient plus que
        le rendu lui-même.
        """
        self.ensure_one()
        model3d = self._web_model3d()
        values = self._web_values()
        return {
            "productName": self.product_tmpl_id.display_name,
            "state": self.state,
            "attributes": self._web_attribute_lines(),
            "price": self.get_cfg_price(),
            # ⓘ La définition porte la FORME, la portée porte les VALEURS : c'est
            # la séparation de D-163, et elle vaut ici comme dans l'éditeur.
            "definition": model3d.to_definition(values) if model3d else None,
            "scope": model3d.get_attribute_scope(values) if model3d else {},
        }
