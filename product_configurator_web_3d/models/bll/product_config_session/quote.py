"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
import logging
from odoo import api, models
from odoo.addons.product_editor.models.bll.product_model3d.structure import EngineCountError

_logger = logging.getLogger(__name__)


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def action_open_3d_page(self):
        """L'action qui EMMÈNE à la page 3D de cette configuration.

        Un seul endroit fabrique cette URL : la fiche produit et la ligne de
        devis y passent toutes les deux. Le jeton reste la seule identité, même
        au back-office — c'est ce qui permet d'ouvrir la même page, pour un
        interne comme pour un client (D-091).

        ⚠️ **UN DIALOGUE, PAS UN ONGLET** (D-262) : un onglet fait perdre de vue ce
        qu'on faisait, au devis comme ailleurs. Une action CLIENTE en `target: "new"` :
        Odoo l'enveloppe lui-même.

        ⓘ **L'état part AVEC l'action.** On vient de le calculer ; le redemander
        au montage coûterait un aller-retour pour la même réponse, et la page
        attendrait devant un écran vide (D-249).

        ⓘ Le JETON reste la seule identité, au back-office comme ailleurs
        (D-091) : c'est lui qui permet d'ouvrir la même configuration pour un
        interne et pour un client. L'URL publique existe toujours et se partage.

        ⓘ **`footer: False`** (D-263) : la croix suffit. Le pied qu'Odoo ajoute
        d'office ne porte qu'un bouton « Ok » qui ferme, exactement comme la
        croix du titre ; deux façons de faire le même geste, et l'une des deux
        ressemble à une validation qu'elle n'est pas. C'est `action_service`
        qui lit ce drapeau dans le contexte (`web/…/actions/action_service.js`).
        """
        self.ensure_one()
        self._ensure_access_token()
        return {
            "type": "ir.actions.client",
            "tag": "product_configurator_web_3d.configurator",
            "name": self.product_tmpl_id.display_name,
            "target": "new",
            "context": {"footer": False},
            "params": {
                "token": self.access_token,
                "state": self.web_state(),
            },
        }

    def _web_on_open(self, **options):
        """Ce qu'un module pose sur la session quand le back-office l'ouvre — rien ici."""

    def _web_pricing(self):
        """La liste de prix et la date qui chiffrent la page — `None` : celles de qui regarde.

        ⓘ Un module qui ouvre la page pour une COMMANDE rend les siennes (D-537).
        """
        return None, None

    def web_separate_lines(self, definition=None):
        """Les lignes de devis À PART de cette configuration — D-368.

        `[{attributeId, valueId, linkId, name, productId, qty, price}]` : une par question
        vendue à part dont la réponse désigne un produit. « Sans bumper » (sans produit)
        n'en donne aucune.

        ⓘ **L'article et son prix** : la variante née à la confirmation (`child_variants`) ;
        avant, celle de la COMBINAISON que la pièce répond (sa matière comprise — la couleur
        du bumper change son prix si la valeur porte un supplément), sinon celle que la
        valeur désigne.

        ⓘ **La quantité** (D-375) : le nombre de POSES des liens permutés par la question,
        répétitions et miroirs compris — le moteur les compte, dans Node
        (`product.model3d._count_poses`). Une pose RÉFLÉCHIE d'une pièce chirale qui a un
        jumeau passe sur une ligne à part, sous l'article du jumeau (D-074, D-357). Sans
        décompte (Node absent), la quantité d'avant : le nombre de liens — dit au journal.
        """
        self.ensure_one()
        apart = self.product_tmpl_id._sale_separately_attribute_ids()
        if not apart:
            return []
        model3d = self._web_model3d()
        values = self._web_values()
        if definition is None and model3d:
            definition = model3d.to_definition(values, link_answers=self._web_link_answers())
        Model3d = self.env["product.model3d"].sudo()
        Link = self.env["product.model3d.component"].sudo()
        answers_by_node = (Model3d._node_answers(definition, model3d.get_attribute_scope(values))
                           if model3d else {})
        nodes_by_attr = {}

        def walk(node):
            for child in node.get("children") or []:
                link = Link.browse(child.get("linkId") or 0).exists()
                if link and link.swap_attribute_id.id in apart:
                    nodes_by_attr.setdefault(link.swap_attribute_id.id, []).append(child)
                walk(child)

        walk(definition or {})
        poses = None
        if model3d and nodes_by_attr:
            poses = Model3d._count_poses(definition, model3d.get_attribute_scope(values))
            if poses is None:
                _logger.warning("session %s: the engine did not count the poses; parts sold "
                                "separately are counted one per placement", self.id)
        variants = self.child_variants or {}
        Product = self.env["product.product"].sudo()
        # ⚠️ **LA MÊME LISTE DE PRIX QUE LE PRODUIT** (`get_cfg_price`) : sans elle, la page
        # annonçait le bumper au prix catalogue (1,00) et le panier le facturait à 0,00 —
        # mesuré sur une copie de fabk18, dont la liste « Par défaut » porte des règles.
        pricelist = self._web_pricing()[0]
        if pricelist is None:
            pricelist = self.env.user.partner_id.property_product_pricelist
        out = []
        for value in self.value_ids.filtered(lambda v: v.attribute_id.id in apart):
            if not value.product_id:
                continue
            nodes = nodes_by_attr.get(value.attribute_id.id) or []
            straight, reflected = self._web_pose_counts(nodes, poses)
            product, price, name = value.product_id.sudo(), None, None
            twin = None
            if nodes:
                node = nodes[0]
                link_id = node.get("linkId")
                model = Model3d.browse(node.get("model3dId")).exists()
                tmpl = model.product_tmpl_id
                value_ids = []
                if tmpl:
                    value_ids = self._web_child_value_ids(
                        tmpl, answers_by_node.get(node.get("id")) or {},
                        self._web_child_custom(link_id), node, link_id)
                if str(link_id) in variants:
                    product = Product.browse(variants[str(link_id)])
                elif tmpl:
                    found, price, name = self._web_combination(tmpl, value_ids, pricelist)
                    # ⚠️ Sans variante encore née, AUCUN article : retomber sur celui de
                    # la valeur afficherait « Bumper (Bleu) » au prix du Rouge.
                    product = found or self.env["product.product"]
                if reflected:
                    twin = self._web_twin_line(model, value_ids, str(link_id) in variants,
                                               pricelist, link_id)
                if not twin:
                    straight, reflected = straight + reflected, 0
            base = {"attributeId": value.attribute_id.id, "valueId": value.id,
                    "linkId": nodes[0].get("linkId") if nodes else None}
            # ⓘ Toujours au moins une : une pièce choisie se vend, même sans pose
            # dans la scène (option sans 3D, nature ④).
            if straight or not twin:
                out.append(dict(base,
                                name=product.display_name if product else name,
                                productId=product.id or None,
                                qty=max(straight, 1),
                                price=price if price is not None
                                else self._web_price(product, pricelist)))
            if twin:
                out.append(dict(base, mirrored=True, qty=reflected, **twin))
        return out

    def _web_no_variant_ptav_ids(self):
        """Les `product.template.attribute.value` de TOUTES les réponses « sans variante » —
        celles qui vont sur la LIGNE de commande, et non dans l'article (W-99 / D-393).

        ⚠️ Depuis l'option A, l'article ne porte plus ces réponses : une seule qui ne serait
        pas transmise, et la boutique y mettrait d'office la PREMIÈRE valeur (« Mat » au lieu
        de « Brillant », mesuré). Les questions vendues à part (D-368) en sont un cas.
        """
        self.ensure_one()
        chosen = self.value_ids.filtered(lambda v: v.attribute_id.create_variant == "no_variant")
        if not chosen:
            return []
        return self.product_tmpl_id.attribute_line_ids.product_template_value_ids.filtered(
            lambda ptav: ptav.product_attribute_value_id in chosen).ids

    @api.model
    def _web_price(self, product, pricelist):
        """Le prix d'un article (ou d'un gabarit) par la liste de prix donnée, sinon catalogue."""
        if pricelist:
            return pricelist._get_product_price(product, 1.0)
        return product._get_contextual_price()

    @api.model
    def _web_combination(self, tmpl, value_ids, pricelist=None):
        """`(variante existante | vide, prix, nom)` d'une combinaison — SANS créer la variante.

        ⓘ Une variante dynamique n'existe qu'une fois commandée : afficher un prix ne doit
        pas en créer une. Sans elle, le prix est celui du gabarit plus les suppléments de
        la combinaison, par la liste de prix — la même voie que `get_cfg_price`
        (`current_attributes_price_extra`).
        """
        wanted = set(value_ids)
        combination = tmpl.attribute_line_ids.product_template_value_ids.filtered(
            lambda ptav: ptav.product_attribute_value_id.id in wanted)
        variant = tmpl._get_variant_for_combination(combination)
        if variant:
            return variant, self._web_price(variant, pricelist), variant.display_name
        extra = sum(combination.mapped("price_extra"))
        # ⓘ Le nom que la variante PORTERA — la règle du cœur (`_get_combination_name`).
        label = combination._get_combination_name()
        return (self.env["product.product"],
                self._web_price(tmpl.with_context(current_attributes_price_extra=[extra]),
                                pricelist),
                "%s (%s)" % (tmpl.display_name, label) if label else tmpl.display_name)

    @api.model
    def _web_value_of_entry(self, line, entry):
        """La VALEUR d'une ligne qui porte cette réponse de portée — ou rien — D-368.

        ⓘ Une entrée de portée est l'IDENTIFIANT de la valeur pour une question discrète, et
        le NOMBRE pour une question numérique (`to_scope_entry`, D-080). La page coche une
        valeur : on retrouve donc la valeur offerte qui porte ce nombre ou cet identifiant.
        Une réponse qu'aucune valeur offerte ne porte (une saisie, un nombre hors liste) ne
        coche rien — plutôt qu'une voisine plausible.
        """
        if entry is None or entry is False:
            return None
        values = line.value_ids
        if line.attribute_id.is_numeric():
            for value in values:
                try:
                    if float(str(value.name).replace(",", ".")) == float(entry):
                        return value.id
                except (TypeError, ValueError):
                    continue
            return None
        try:
            entry = int(entry)
        except (TypeError, ValueError):
            return None
        return entry if entry in values.ids else None

    def _web_values(self):
        """`{attribut → réponse}` — la forme que le moteur 3D attend (D-163).

        ⚠️ **Une question NUMÉRIQUE reçoit le NOM de la valeur, jamais son
        identifiant.** `to_scope_entry` traduit une réponse numérique par
        `parse_number(brut)` : l'`id` de la valeur « 2 » y entrait comme **292**,
        un nombre parfaitement valide et faux. La plaque du JeNo se construisait
        donc à 292 mm d'épaisseur — mesuré : `scope = {'__attribute_144': 292.0}`
        (D-262).

        ⓘ Le danger était ANNONCÉ, à un autre endroit : *« les options portent
        leur libellé, jamais leur identifiant »* (`answer_field`). La règle
        valait ici aussi, et rien ne la tenait.

        ⓘ Pour une question DISCRÈTE, l'identifiant reste la bonne forme : c'est
        lui que `resolve_answer` retrouve sans ambiguïté, là où deux valeurs
        peuvent porter le même libellé sur deux attributs différents.
        """
        self.ensure_one()
        values = {
            value.attribute_id.id: (
                value.name if value.attribute_id.is_numeric() else value.id
            )
            for value in self.value_ids
        }
        # ⚠️ **ET CE QUE LE CLIENT A TAPÉ** (D-353) — une largeur saisie doit changer la
        # pièce. Un nombre entre par sa forme rangée ; un TEXTE qui ne désigne aucune
        # valeur ne résout rien (`to_scope_entry` rend `None`) : sa clé reste hors de la
        # portée, et une condition qui le cite est ignorée plutôt que fausse (D-150).
        for attr_id, text in self._web_root_custom().items():
            values.setdefault(attr_id, text)
        return values

    def _notify_configuration_changed(self):
        """Prévenir ceux qui regardent que la configuration a changé — D-253.

        ⚠️ **UN SIGNAL, PLUS L'ÉTAT COMPLET** ([[L-451]]). Le message
        portait tout `web_state()` — environ 500 Ko sur le JeNo, définition 3D
        comprise — et il coûtait trois fois :
          · un second `web_state()` à CHAQUE clic, calculé dans le `write` (0,47 s
            sur 0,66 s au profil), en plus de celui de la réponse ;
          · une ligne d'environ 500 Ko dans `bus_bus` à chaque clic ;
          · un envoi websocket NON compressé à chaque spectateur — y compris à
            l'auteur, qui venait de recevoir le même état en réponse.

        Le signal nomme l'AUTEUR (le porteur de l'onglet qui a agi, `cfg_author`,
        posé par la route) : sa page l'ignore, les autres relisent
        `/configurator/state`, qui rend exactement ce qu'elles appliquaient. Sans
        auteur — une écriture du backend —, tout le monde relit.
        """
        self.ensure_one()
        self._bus_send("configurator_state",
                       {"author": self.env.context.get("cfg_author") or None})
        return super()._notify_configuration_changed()

    def _web_after_confirm(self):
        """Ce qui suit la confirmation, là où la configuration ATTERRIT.

        Vide ici, et c'est voulu : le cœur de l'interface ne sait pas ce qu'est
        un devis. `product_configurator_web_3d_sale` s'y branche pour écrire la
        ligne. Un autre atterrissage (un panier, une demande) s'y brancherait
        pareil, sans toucher à cette classe.
        """
        return True

    def _web_reopen_if_open_quote(self):
        """Rouvrir une configuration CONFIRMÉE tant que son devis n'est pas une commande — D-371.

        ⓘ **Rien n'est joué au stade du devis** : la variante d'une ligne
        n'est qu'un nom posé sur des réponses, et c'est la COMMANDE qui l'engage. D-190
        fermait la configuration dès sa confirmation ; c'est désormais la commande qui la
        verrouille.

        Sans le module de vente, rien ne dit qu'un devis existe : la configuration reste
        close, comme avant. `product_configurator_web_3d_sale` répond pour les lignes de devis.

        :returns: vrai si la configuration a été rouverte
        """
        return False

    def web_confirm(self, lean=False):
        """Terminer la configuration : la variante naît, la session se ferme.

        ⓘ `lean` : la page part ensuite (panier, devis) et ne lit que `web_confirm_summary` (D-561).

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
        # ⚠️ Hors grille, le prix retomberait sur le plus bas de la grille : refusé (D-537).
        out_of_grid = self._out_of_grid_message(date=self._web_pricing()[1])
        if out_of_grid:
            return {"error": "out_of_grid", "message": out_of_grid}
        # ⚠️ Le compte du moteur est EXIGÉ ici : un compte manqué donnerait une quantité ou une variante fausse sur la commande (D-457, Q-1).
        try:
            with self.env.cr.savepoint():
                confirming = self.with_context(engine_count_required=True)
                confirming.action_confirm()
                confirming._web_confirm_children()
                confirming._web_after_confirm()
        except EngineCountError as exc:
            return {"error": "engine", "message": exc.args[0]}
        # ⓘ Close, la configuration n'a plus de conducteur : la main est rendue (D-371).
        self._release_hand()
        # ⚠️ Pas l'état complet pour une page qui part : il coûtait les deux tiers de la confirmation (D-561).
        return self.web_confirm_summary() if lean else self.web_state()

    def web_confirm_summary(self):
        """Ce que la page lit d'une confirmation après laquelle elle part : la variante, ses lignes à part — D-561.

        ⚠️ Toute clé lue par la page après une confirmation `lean` doit être ici, ou dans une extension (photo, panier).
        """
        self.ensure_one()
        return {
            "state": self.state,
            "productId": self.product_id.id or None,
            "separateLines": self.web_separate_lines(),
            "noVariantPtavIds": self._web_no_variant_ptav_ids(),
        }

    def _web_product_url(self):
        """L'adresse publique du produit — ou `None` s'il n'y a pas de site.

        ⚠️ **Le champ n'existe QUE si `website` est installé** (`website.published.mixin`),
        et ce module n'en dépend pas — il sert aussi un back-office sans boutique. On teste
        donc sa présence : absent, la page ne dessine pas de croix, plutôt que d'en dessiner
        une qui ne mène nulle part.
        """
        self.ensure_one()
        tmpl = self.product_tmpl_id
        return tmpl.website_url if "website_url" in tmpl._fields else None
