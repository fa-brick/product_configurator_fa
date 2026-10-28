"""Ce qu'exécute `product.attribute` (BLL, D-541)."""
from ast import literal_eval
from psycopg2 import IntegrityError
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    @api.depends("product_filter_domain", "value_type")
    def _compute_product_filter_count(self):
        for attribute in self:
            filtre = (attribute.product_filter_domain or "").strip()
            if (not attribute.dynamic_values or attribute.value_type != "product"
                    or not filtre or filtre == "[]"):
                attribute.product_filter_count = 0
                continue
            # ⚠️ CE CALCUL NE DOIT PAS LEVER. Il tourne pendant la SAISIE, à chaque
            # frappe dans l'éditeur de domaine : un domaine à moitié écrit est la
            # règle, pas l'exception. Une exception ici casserait le formulaire au
            # lieu d'attendre. Le refus, lui, se fait à l'enregistrement — c'est
            # `_check_product_filter` qui dit non, avec ses mots.
            try:
                attribute.product_filter_count = self.env[
                    "product.product"
                ].search_count(literal_eval(filtre))
            except Exception:
                attribute.product_filter_count = 0

    @api.constrains("value_type", "create_variant")
    def _check_no_variant_lines(self):
        """W-99 / D-393 — changer la nature d'un attribut revérifie les lignes des produits
        configurables qui le posent (`_check_no_variant_on_configurable`)."""
        lines = self.env["product.template.attribute.line"].search([("attribute_id", "in", self.ids)])
        lines._check_no_variant_on_configurable()

    @api.onchange("custom_type")
    def onchange_custom_type(self):
        if self.custom_type in self._get_nosearch_fields():
            self.search_ok = False

        # ⚠️ Les bornes ne sont plus ici (D-089) : « Largeur » est partagée par
        # un portail et une porte de garage, une borne globale ne peut être
        # juste pour personne. Le nettoyage des bornes devenues sans objet se
        # fait donc sur la LIGNE, dans `onchange_attribute`.
    @api.onchange("val_custom")
    def onchange_val_custom_field(self):
        if not self.val_custom:
            self.custom_type = False

    @api.constrains("dynamic_values", "value_type")
    def _check_dynamic_values(self):
        for attribute in self:
            if attribute.dynamic_values and attribute.value_type != "product":
                raise ValidationError(
                    self.env._(
                        "Only an attribute whose values designate a Product can "
                        "have dynamic values: a filter proposes products, and "
                        "nothing else."
                    )
                )

    @api.onchange("value_type")
    def _onchange_value_type_clears_dynamic(self):
        # ⚠️ Sans ce nettoyage, quitter le type « produit » laisserait la coche —
        # et son filtre — en base, invisibles, et le refus tomberait sur un champ
        # que l'utilisateur ne voit plus. Même geste qu'en D-194.
        if self.value_type != "product":
            self.dynamic_values = False
            self.product_filter_domain = "[]"

    @api.onchange("dynamic_values")
    def _onchange_dynamic_values_clears_filter(self):
        # ⓘ Décocher, c'est revenir à une liste tenue à la main : le filtre n'a
        # plus d'objet, et le garder ferait croire qu'il agit encore.
        if not self.dynamic_values:
            self.product_filter_domain = "[]"

    @api.constrains("product_filter_domain", "value_type")
    def _check_product_filter(self):
        for attribute in self:
            filtre = (attribute.product_filter_domain or "").strip()
            if not filtre or filtre == "[]":
                continue
            # ⚠️ Première barrière : un filtre n'a de sens que si les valeurs
            # désignent un produit. Ailleurs il ne proposerait rien à personne.
            if attribute.value_type != "product":
                raise ValidationError(
                    self.env._(
                        "A product filter only makes sense when the values of "
                        "this attribute designate a Product."
                    )
                )
            # ⚠️ Seconde barrière : le filtre doit s'ÉVALUER. Sans cela, un
            # domaine invalide se découvre au moment de configurer — devant le
            # client — et ressemble à une panne, pas à une saisie.
            try:
                self.env["product.product"].search(
                    literal_eval(filtre), limit=1
                )
            except Exception as exc:
                raise ValidationError(
                    self.env._(
                        "This product filter cannot be applied: %s", exc
                    )
                ) from exc

    # TODO prevent the same attribute from being defined twice on the
    # attribute lines
    @api.constrains("custom_type", "search_ok")
    def check_searchable_field(self):
        for attribute in self:
            nosearch_fields = attribute._get_nosearch_fields()
            if attribute.custom_type in nosearch_fields and attribute.search_ok:
                raise ValidationError(
                    self.env._(
                        "Selected custom field type '%s' is not searchable",
                        attribute.custom_type,
                    )
                )

    def copy(self, default=None):
        """Add ' (Copy)' in name to prevent attribute
        having same name while copying"""
        if not default:
            default = {}
        new_attrs = self.env["product.attribute"]
        for attr in self:
            default.update({"name": attr.name + " (copy)"})
            new_attrs += super(ProductAttribute, attr).copy(default)
        return new_attrs

    @api.model_create_multi
    def create(self, vals_list):
        """⚠️ **UN ATTRIBUT CRÉÉ AVEC SON FILTRE MATÉRIALISE AUSSI.**

        La matérialisation ne vivait que dans `write` : poser le filtre à la
        CRÉATION ne proposait rien, et la liste restait vide jusqu'à la première
        modification. ⓘ Trouvé par la couture de la rétractation — pas à
        l'écran, cette fois.
        """
        attributs = super().create(vals_list)
        for attribut in attributs.filtered("dynamic_values"):
            attribut._materialise_proposed_values()
        return attributs

    def write(self, vals):
        """⚠️ LA PURGE SE FAIT ICI, et non dans un `onchange`.

        Un `onchange` ne joue que dans le dialogue vue↔serveur : un import, un
        script ou une écriture ORM laisseraient les valeurs incohérentes, et la
        garde de D-196 refuserait tout enregistrement ultérieur. C'est la seconde
        barrière, celle qui ne dépend pas de l'interface (D-080).

        ⓘ On n'agit que si le type CHANGE VRAIMENT : réécrire la même valeur ne
        doit rien effacer.
        """
        nouveau = vals.get("value_type")
        if nouveau:
            concernes = self.filtered(lambda a: a.value_type != nouveau)
            concernes.value_ids._purge_designation(nouveau)
        res = super().write(vals)
        # ⚠️ **LE FILTRE SE MATÉRIALISE DÈS QU'IL EST POSÉ** (D-222) : sinon les
        # valeurs n'apparaissent qu'à la première ouverture de l'assistant, et la
        # page d'attribut montre une liste vide quand le filtre annonce des produits.
        #
        # ⓘ L'opération est idempotente (D-221) : la refaire ne crée rien.
        if "product_filter_domain" in vals or "dynamic_values" in vals:
            for attribute in self.filtered("dynamic_values"):
                attribute._materialise_proposed_values()
        return res

    def action_open_proposed_values(self):
        """Montre les VALEURS que ce filtre propose — dans un dialogue.

        ⚠️ **DES VALEURS, PAS DES PRODUITS** (D-227) : c'est ce que l'attribut porte
        réellement. ⓘ Elles existent déjà : poser le filtre les matérialise (D-222),
        ce dialogue n'a rien à créer.

        ⓘ Un dialogue, comme pour les valeurs (D-206) : on revient là où on l'a
        ouvert, sans perdre la fiche d'attribut qu'on est en train de régler.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Values proposed by the filter"),
            "res_model": "product.attribute.value",
            "view_mode": "list",
            "views": [(False, "list")],
            "domain": [
                ("attribute_id", "=", self.id),
                ("product_id", "in", self._proposed_products().ids),
            ],
            "target": "new",
            # ⚠️ **NI CRÉER NI SUPPRIMER ICI** : cette liste est le RÉSULTAT d'un
            # filtre — une valeur ajoutée à la main n'en ferait pas partie, une
            # valeur retirée reviendrait au prochain enregistrement (D-228).
            #
            # ⓘ La liste tenue à la main, elle, reste l'onglet « Valeurs
            # d'attribut » — c'est là qu'on ajoute et qu'on retire.
            "context": {"create": False, "delete": False},
        }

    @api.model
    def _get_nosearch_fields(self):
        """Return a list of custom field types that do not support searching"""
        return ["binary"]

    def _materialise_proposed_values(self):
        """Donne une VALEUR à chaque produit proposé — C3, D-221.

        ⚠️ **QJ : la valeur choisie est MATÉRIALISÉE.** C'est ce qui rend la liste
        dynamique tenable : ce que le client retient devient une
        `product.attribute.value` ordinaire, portant son `product_id` — et **tout
        ce qui pend à une valeur continue de fonctionner** : prix, archivage,
        exclusions, historique des commandes, identité d'une variante.

        ⚠️ **IDEMPOTENT, et c'est essentiel.** L'assistant appelle ceci à chaque
        ouverture : sans réemploi par `product_id`, chaque visite créerait un
        jumeau, et le catalogue enflerait d'une valeur par consultation.

        ⓘ `configurator_generated` marque ces valeurs comme le fait la saisie
        libre : le ménage existant archive celles que plus rien n'emploie. Une
        valeur proposée mais jamais retenue finit donc par s'effacer d'elle-même.
        """
        self.ensure_one()
        proposees = self._materialise_products(self._proposed_products())
        self._retract_stale_values(proposees)
        return proposees

    def _retract_stale_values(self, proposees):
        """Retire ce qu'un filtre PRÉCÉDENT proposait et que celui-ci ne propose plus.

        ⚠️ Sans rétractation, chaque essai de filtre laisse ses valeurs derrière lui,
        et la liste contredit le compteur qui l'annonce (D-228). Le ménage existant ne
        passe qu'après 90 jours — trop tard pour un réglage qu'on ajuste en direct.

        **⚠️ CE QUI EST ÉPARGNÉ, et pourquoi chaque exception compte :**

        · **une valeur écrite à la main** — elle n'a jamais été proposée par un
          filtre, ce n'est pas à lui de la reprendre ;
        · **une valeur RETENUE sur un produit** — QJ pose que la valeur choisie
          est matérialisée : la retirer parce que le filtre a changé casserait la
          ligne d'un produit en service, en silence ;
        · **un produit désigné par une CONDITION** (C4, D-201) — la règle se
          résout par cette valeur ; l'effacer rendrait la condition vide, donc
          toujours fausse, sans un mot.

        ⓘ On **supprime** ce qui peut l'être et on **archive** le reste, selon la
        même prévision que le champ « On removal » (`removal_effect`) :
        une valeur déjà portée par une variante vendue doit rester lisible.
        """
        self.ensure_one()
        # ⚠️ Hors du régime dynamique, on ne retire RIEN : la liste est alors
        # tenue à la main, et le filtre n'a plus voix au chapitre (D-218).
        if not self.dynamic_values or self.value_type != "product":
            return self.env["product.attribute.value"]

        designes = self.env["product.config.domain.line"].search(
            [("attribute_id", "=", self.id)]
        ).product_ids
        retenues = self.env["product.template.attribute.line"].search(
            [("attribute_id", "=", self.id)]
        ).value_ids

        obsoletes = self.value_ids.filtered(
            lambda v: v.configurator_generated
            and v.product_id
            and v not in proposees
            and v not in retenues
            and v.product_id not in designes
        )
        if not obsoletes:
            return obsoletes
        # ⚠️ **ON N'EFFACE PAS CE QUI EST RÉFÉRENCÉ.** Une valeur portée par une
        # `product.template.attribute.value` — même archivée — est protégée en
        # base par un `ondelete='restrict'` : la supprimer lèverait. C'est le
        # même raisonnement que le ménage de fond (`_gc_configurator_values`),
        # et la même conclusion : archiver garde l'historique lisible.
        portees = (
            self.env["product.template.attribute.value"]
            .with_context(active_test=False)
            .search([("product_attribute_value_id", "in", obsoletes.ids)])
            .product_attribute_value_id
        )
        (obsoletes - portees).unlink()
        portees.active = False
        return obsoletes

    def _materialise_products(self, produits):
        """Donne une valeur à CHAQUE produit fourni — le geste, sans la source.

        ⓘ Extrait de `_materialise_proposed_values` pour C4 : une condition qui
        désigne des produits (D-201) a besoin du même geste, mais sur un ensemble
        **choisi à la main** plutôt que sur le résultat d'un filtre. Deux copies
        de cette mécanique auraient fini par diverger sur la réanimation ou sur
        le marquage.
        """
        self.ensure_one()
        if not produits:
            return self.env["product.attribute.value"]

        value_obj = self.env["product.attribute.value"]
        existantes = value_obj.with_context(active_test=False).search([
            ("attribute_id", "=", self.id),
            ("product_id", "in", produits.ids),
        ])
        par_produit = {v.product_id.id: v for v in existantes}

        # ⓘ Une valeur ARCHIVÉE est ressuscitée plutôt que dupliquée — même geste
        # que pour une saisie libre qui revient (D-082).
        a_reveiller = existantes.filtered(lambda v: not v.active)
        if a_reveiller:
            a_reveiller.active = True

        manquants = produits.filtered(lambda p: p.id not in par_produit)
        for produit in manquants:
            par_produit[produit.id] = value_obj.create({
                "attribute_id": self.id,
                "name": produit.display_name,
                "product_id": produit.id,
                "configurator_generated": True,
            })
        return value_obj.browse([par_produit[p.id].id for p in produits])

    def _proposed_products(self):
        """Les produits que ce filtre PROPOSE — rien de plus.

        ⓘ Sans filtre, aucun produit n'est proposé : un attribut de type produit
        dont on n'a rien dit ne doit pas offrir le catalogue entier.
        """
        self.ensure_one()
        filtre = (self.product_filter_domain or "").strip()
        # ⚠️ Le MODE d'abord : une liste tenue à la main ne propose rien, même si
        # un filtre traîne en base — sinon décocher « valeurs dynamiques »
        # laisserait le filtre agir dans l'ombre.
        if not self.dynamic_values:
            return self.env["product.product"]
        if self.value_type != "product" or not filtre or filtre == "[]":
            return self.env["product.product"]
        return self.env["product.product"].search(literal_eval(filtre))

    def _is_numeric_custom(self):
        """Un attribut dont la valeur EST un nombre.

        ⚠️ **Le corps a DÉMÉNAGÉ, le nom reste.** La même question se pose
        désormais depuis l'éditeur 3D, qui ne peut pas dépendre d'ici (D-075) :
        `product_attribute_advanced` porte donc `is_numeric()`, et cette méthode s'y
        adosse. Deux corps identiques dans deux modules divergeraient au premier format
        ajouté — c'est [[L-034]], et c'est exactement ce que le module partagé existe
        pour éviter.

        ⓘ Le nom privé survit parce que cinq points d'appel le citent, et qu'ils n'ont
        aucune raison de changer : ce qui devait bouger, c'est l'endroit où la règle est
        écrite, pas la façon de la poser.
        """
        self.ensure_one()
        return self.is_numeric()

    # ⓘ **`canonical_custom_value` et `format_custom_value` ONT DÉMÉNAGÉ** vers
    # `product_attribute_advanced`. Elles ne lisent que ce qu'il
    # porte — le format, l'unité, et le lecteur de nombre — et l'ÉDITEUR en a
    # besoin sans le configurateur : c'est lui qui affiche « 2,5 mm » dans ses
    # listes de valeurs, et il ne peut pas dépendre d'un module AGPL-3 (D-075).
    # Elles restent appelables ici, par héritage, et D-160 tient toujours : un
    # seul formateur, porté par l'ATTRIBUT.
    def _resolves_to_values(self):
        """Une saisie sur cet attribut se RANGE-t-elle en valeur d'attribut ?

        La question n'a pas besoin d'un champ neuf : `create_variant` la porte
        déjà. En `no_variant`, la valeur ne peut pas entrer dans l'identité
        d'une variante — la ranger ne servirait à rien. Partout ailleurs, elle
        le peut, et c'est tout l'objet de D-081 : le stock ne sait distinguer
        deux portes que par leurs valeurs d'attribut.

        ⚠️ **LE TEXTE AUSSI, comme le nombre** (D-353). Seul le libellé est
        concerné : une réponse qui désigne un produit ou une matière ne se tape pas
        au clavier. Et le `no_variant` reste la porte des saisies qui ne doivent
        pas devenir un article — des prénoms, une dédicace : elles restent sur la
        ligne de commande, par la session.
        """
        self.ensure_one()
        return self.value_type == "value" and self.create_variant != "no_variant"

    # ⓘ `normalize_custom_text` vit dans `product_attribute_advanced` : l'éditeur la lit aussi,
    #   pour le texte que dessine la forme Texte (W-136). C'est la COMPARAISON qui ignore la
    #   casse, pas le rangement (`find_custom_value`).
    def canonical_custom_answer(self, raw):
        """La forme RANGÉE d'une saisie, nombre ou texte — ou `None` si elle est vide.

        ⚠️ Un nombre illisible ressort tel quel : c'est `validate_custom_val` qui le
        refuse, avec un message. Le ranger à `None` ferait croire à une absence de
        réponse, et la question retomberait en silence sur son défaut ([[L-218]]).
        """
        self.ensure_one()
        if self.is_numeric() or self.is_ranges():
            # ⓘ Des PLAGES (W-102) ont aussi une forme canonique — `54, 3-34` se range
            # `3-34, 54` —, donc une seule valeur pour une seule réponse.
            text = self.normalize_custom_text(raw)
            return self.canonical_custom_value(text) if text else None
        return self.normalize_custom_text(raw) or None

    def find_custom_value(self, raw, values=None):
        """La valeur EXISTANTE qu'une saisie désigne — ou un ensemble vide.

        ⚠️ **COMPARER AVANT DE CRÉER** (D-353, arbitrage 2). Un nombre se compare sur
        sa forme canonique (`18`, `18,0` et ` 18 ` sont une seule valeur, D-160) ;
        un texte, espaces réduits et **casse ignorée** — « chêne » reprend « Chêne ».

        ⚠️ **Le libellé dans la langue du visiteur ET en anglais.** L'index d'unicité
        porte sur `name->>'en_US'` au caractère près : il empêche le doublon exact,
        pas « Paul » contre « paul », ni une valeur saisie en français dont le terme
        source est anglais. C'est donc ici, et non en base, que se décide la
        réutilisation.

        :param values: où chercher — par défaut TOUTES les valeurs de l'attribut,
            archivées comprises (une valeur qui revient est la même valeur).
        """
        self.ensure_one()
        Value = self.env["product.attribute.value"]
        if values is None:
            values = Value.with_context(active_test=False).search(
                [("attribute_id", "=", self.id)]
            )
        wanted = self.canonical_custom_answer(raw)
        if wanted is None:
            return Value
        if self.is_numeric():
            number = self.parse_number(wanted)
            if number is None:
                return Value

            def same(value):
                return any(
                    self.parse_number(name) == number
                    for name in (value.name, value.with_context(lang="en_US").name)
                )
        else:
            needle = wanted.casefold()

            def same(value):
                return any(
                    self.normalize_custom_text(name).casefold() == needle
                    for name in (value.name, value.with_context(lang="en_US").name)
                )

        return values.filtered(same)[:1]

    def resolve_custom_value(self, raw):
        """Rend LA valeur d'attribut d'une saisie — nombre ou texte — en la créant au besoin.

        La même règle pour les deux (D-353) : réutiliser d'abord, créer ensuite,
        ressusciter une valeur archivée plutôt que la doubler. Le nombre garde son
        chemin, qui pose sa forme canonique et sa séquence.
        """
        self.ensure_one()
        Value = self.env["product.attribute.value"]
        if self.is_numeric():
            number = self.parse_number(self.canonical_custom_answer(raw))
            return self.resolve_numeric_value(number) if number is not None else Value
        text = self.canonical_custom_answer(raw)
        if not text:
            return Value
        existing = self.find_custom_value(text)
        if existing:
            if not existing.active:
                existing.sudo().active = True
            return existing
        vals = {"attribute_id": self.id, "name": text, "configurator_generated": True}
        try:
            with self.env.cr.savepoint():
                return Value.sudo().create(vals).with_env(self.env)
        except IntegrityError:
            # Le même texte, écrit au même instant par quelqu'un d'autre : la base
            # a tranché, on reprend ce qu'elle a gardé.
            return self.find_custom_value(text)

    def resolve_numeric_value(self, number):
        """Rend LA valeur d'attribut qui porte ce nombre — en la créant au besoin.

        ⚠️ Le motif « je cherche, sinon je crée » est un *check-then-insert* :
        deux clients validant 3 200 au même instant passent tous deux le test,
        et le stock se coupe en deux. La contrainte d'unicité en base est ce qui
        tranche vraiment (`init`) ; ici, on rattrape sa violation plutôt que de
        prétendre l'éviter.

        Une valeur ARCHIVÉE est ressuscitée plutôt que dupliquée : le ménage
        archive (D-082), et une largeur qui revient est la même largeur.
        """
        self.ensure_one()
        name = self.canonical_custom_value(number)
        value_obj = self.env["product.attribute.value"]
        domain = [("attribute_id", "=", self.id), ("name", "=", name)]
        existing = value_obj.with_context(active_test=False).search(domain, limit=1)
        if existing:
            if not existing.active:
                existing.active = True
            return existing
        vals = {
            "attribute_id": self.id,
            "name": name,
            "configurator_generated": True,
        }
        try:
            with self.env.cr.savepoint():
                return value_obj.sudo().create(vals).with_env(self.env)
        except IntegrityError:
            # Quelqu'un d'autre a créé la même largeur entre-temps : c'est la
            # base qui l'a dit, et c'est la seule autorité qui pouvait le dire.
            return value_obj.with_context(active_test=False).search(domain, limit=1)

    def _configurator_value_ids(self):
        """Values accepted for attributes in `self`."""
        values = self.value_ids
        if any(self.mapped("val_custom")):
            values += self.env["product.config.session"].get_custom_value_id()
        return values
