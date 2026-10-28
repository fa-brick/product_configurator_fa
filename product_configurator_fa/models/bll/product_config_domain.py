"""Ce qu'exécute `product.config.domain` (BLL, D-541)."""
from odoo import api, models
from odoo.exceptions import ValidationError


class ProductConfigDomain(models.Model):
    _inherit = "product.config.domain"

    ATTRIBUTE_FIELD_PREFIX = "__attribute_"

    PRODUCT_FIELD_PREFIX = "__product_"

    @api.depends("implied_ids")
    def _get_trans_implied(self):
        """Computes the transitive closure of relation implied_ids"""

        def linearize(domains):
            trans_domains = domains
            for domain in domains:
                implied_domains = domain.implied_ids - domain
                if implied_domains:
                    trans_domains |= linearize(implied_domains)
            return trans_domains

        for domain in self:
            domain.trans_implied_ids = linearize(domain)

    def compute_domain(self):
        """Returns a list of domains defined on a
        product.config.domain_line_ids and all implied_ids"""
        # TODO: Enable the usage of OR operators between implied_ids
        # TODO: Add implied_ids sequence field to enforce order of operations
        # TODO: Prevent circular dependencies
        computed_domain = []
        for domain in self:
            lines = domain.trans_implied_ids.mapped("domain_line_ids").sorted()
            if not lines:
                continue
            # ⓘ `_resolved_value_ids` — et non `value_ids` — pour que la forme
            # « produit » (C4, D-201) soit évaluée par le MÊME moteur.
            # ⓘ **L'OPÉRANDE DÉPEND DE L'OPÉRATEUR** : des identifiants de valeurs
            # pour une appartenance, un NOMBRE pour une comparaison (D-267).
            # `validate_domains_against_sels` lit les deux formes.
            def _operande(line):
                if line.condition in line.NUMERIC_CONDITIONS:
                    return line.numeric_value
                return line._resolved_value_ids().ids

            for line in lines[:-1]:
                if line.operator == "or":
                    computed_domain.append("|")
                computed_domain.append(
                    (line.attribute_id.id, line.condition, _operande(line))
                )
            # ensure 2 operands follow the last operator
            computed_domain.append(
                (lines[-1].attribute_id.id, lines[-1].condition, _operande(lines[-1]))
            )
        return computed_domain

    @api.model
    def _attribute_field_name(self, attribute):
        """Le nom du champ FICTIF qui représente un attribut dans l'éditeur.

        Même préfixe que les champs dynamiques d'OCA (`__attribute_<id>`) :
        deux conventions pour la même chose finiraient par diverger.
        """
        return f"{self.ATTRIBUTE_FIELD_PREFIX}{attribute.id}"

    @api.model
    def _product_field_name(self, attribute):
        """Le champ fictif d'une feuille « PRODUIT » — C4, D-201.

        ⚠️ **Un préfixe distinct, et c'est le point.** Rendre une feuille
        « produit » sous le champ des valeurs l'aurait fait revenir de l'éditeur
        en feuille « valeur » : la règle se serait mise à désigner des valeurs
        FIGÉES là où l'auteur avait désigné des produits — le silence exact que
        `from_odoo_domain` existe pour empêcher (D-080).
        """
        return f"{self.PRODUCT_FIELD_PREFIX}{attribute.id}"

    def to_odoo_domain(self):
        """Rend la condition sous la forme que le `DomainSelector` sait lire.

        Le stockage reste celui d'OCA — des ENREGISTREMENTS, jamais du texte
        (D-080). Cette traduction ne vit que le temps d'un aller-retour vers
        l'éditeur.
        """
        self.ensure_one()
        domain = []
        lines = self.domain_line_ids.sorted()
        # ⚠️ Même forme que `compute_domain`, y compris sa bizarrerie : le
        # marqueur « | » précède la ligne QUI LE PORTE, et la DERNIÈRE ligne
        # n'en émet jamais (sinon l'opérateur manquerait d'un opérande). Deux
        # rendus qui divergeraient d'un caractère donneraient deux conditions
        # différentes pour un même enregistrement.
        for line in lines[:-1]:
            if line.operator == "or":
                domain.append("|")
            domain.append(self._leaf_of(line))
        if lines:
            domain.append(self._leaf_of(lines[-1]))
        return domain

    def _leaf_of(self, line):
        """La feuille d'éditeur d'une ligne — selon la forme qu'elle porte."""
        if line.condition in line.NUMERIC_CONDITIONS:
            return (
                self._attribute_field_name(line.attribute_id),
                line.condition,
                line.numeric_value,
            )
        if line.product_ids:
            return (
                self._product_field_name(line.attribute_id),
                line.condition,
                line.product_ids.ids,
            )
        return (
            self._attribute_field_name(line.attribute_id),
            line.condition,
            line.value_ids.ids,
        )

    def _parse_condition_groups(self, domain):
        """Lit un domaine préfixé et rend des GROUPES de feuilles en OU.

        Le stockage sait dire une chose et une seule : **un ET de groupes, dont
        chacun est un OU de feuilles** (D-203 — ET entre les pastilles, OU à
        l'intérieur d'une). Cette lecture accepte exactement cela, et refuse le
        reste plutôt que de l'aplatir : `['|', A, '&', B, C]` dit *A OU (B ET C)*,
        que les lignes ne savent pas garder.

        ⓘ C'est la seconde barrière de D-080, celle qui ne dépend pas de
        l'interface — mais elle refuse désormais sur la STRUCTURE, plus sur la
        présence d'un jeton.
        """
        jetons = list(domain)
        position = 0

        def lire():
            nonlocal position
            if position >= len(jetons):
                raise ValidationError(
                    self.env._("This condition is truncated and cannot be read")
                )
            jeton = jetons[position]
            position += 1
            if jeton == "!":
                raise ValidationError(
                    self.env._("NOT is not supported in a configuration condition")
                )
            if jeton in ("&", "|"):
                return (jeton, lire(), lire())
            return ("leaf", jeton)

        # ⓘ Un domaine peut être une SUITE d'expressions, implicitement liées
        # par ET — c'est la forme la plus courante, et celle que nous écrivons.
        expressions = []
        while position < len(jetons):
            expressions.append(lire())

        def groupes_de(noeud):
            """Les groupes d'un nœud : un ET en produit plusieurs, un OU un seul."""
            genre = noeud[0]
            if genre == "leaf":
                return [[noeud[1]]]
            if genre == "&":
                return groupes_de(noeud[1]) + groupes_de(noeud[2])
            # OU : les deux côtés doivent tenir dans UN seul groupe, sinon la
            # condition mêle les deux liaisons et le stockage la perdrait.
            gauche = groupes_de(noeud[1])
            droite = groupes_de(noeud[2])
            if len(gauche) > 1 or len(droite) > 1:
                raise ValidationError(
                    self.env._(
                        "A configuration condition cannot mix AND inside OR; "
                        "split it into several rules."
                    )
                )
            return [gauche[0] + droite[0]]

        groupes = []
        for expression in expressions:
            groupes.extend(groupes_de(expression))
        return groupes

    def from_odoo_domain(self, domain):
        """Réécrit les lignes de la condition depuis un domaine d'éditeur.

        ⚠️ REFUSE ce que le stockage perdrait. Le `DomainSelector` sait
        exprimer bien plus que les lignes d'OCA ne savent garder — groupes
        imbriqués, autres opérateurs, autres champs. Branché tel quel, il
        laisserait construire une condition que l'enregistrement perdrait EN
        SILENCE (D-080). L'éditeur est restreint en amont ; ce refus est la
        seconde barrière, celle qui ne dépend pas de l'interface.
        """
        self.ensure_one()
        lines = []
        # ⚠️ **LE ET EXPLICITE DOIT ÊTRE ACCEPTÉ** : l'éditeur écrit `['&', A, B]` dès
        # qu'une condition porte DEUX règles ; une suite de feuilles est déjà un ET (D-226).
        #
        # ⚠️ Mais il ne se RETIRE pas non plus à l'aveugle : `['|', A, '&', B, C]`
        # dit *A OU (B ET C)*, quand `['|', A, B, C]` dit *(A OU B) ET C*. Deux
        # conditions différentes. D'où une lecture de la structure, et non un
        # filtrage de jetons.
        for groupe in self._parse_condition_groups(domain):
            for rang, leaf in enumerate(groupe):
                field_name, operator, values = leaf
                # ⓘ L'opérateur d'une ligne gouverne sa jonction avec la
                # SUIVANTE : dans un groupe en OU, toutes sauf la dernière.
                pending_or = rang < len(groupe) - 1
                produits = str(field_name).startswith(self.PRODUCT_FIELD_PREFIX)
                if not produits and not str(field_name).startswith(
                    self.ATTRIBUTE_FIELD_PREFIX
                ):
                    raise ValidationError(
                        self.env._(
                            "A configuration condition can only test attributes, "
                            "not '%(field)s'",
                            field=field_name,
                        )
                    )
                # ⚠️ **UNE COMPARAISON SE RECONNAÎT À SA QUESTION**, pas à son
                # opérateur : `=` sur une question à valeurs veut dire « parmi », `=`
                # sur une question numérique veut dire « égal à ce nombre ». Les
                # confondre stockerait un identifiant de valeur comme un nombre — une
                # règle silencieusement fausse (D-267).
                attribut = self.env["product.attribute"].browse(
                    int(str(field_name)[len(
                        self.PRODUCT_FIELD_PREFIX if produits
                        else self.ATTRIBUTE_FIELD_PREFIX):])
                ) if not produits else self.env["product.attribute"]
                # ⓘ La constante vit sur la LIGNE — c'est elle qui porte la
                # comparaison —, et `self` est ici la condition.
                numeriques = self.env["product.config.domain.line"].NUMERIC_CONDITIONS
                if attribut and attribut.is_numeric() and operator in numeriques:
                    try:
                        nombre = float(values)
                    except (TypeError, ValueError):
                        raise ValidationError(self.env._(
                            "“%(attribute)s” compares to a number: type a number.",
                            attribute=attribut.name)) from None
                    lines.append((0, 0, {
                        "attribute_id": attribut.id,
                        "condition": operator,
                        "operator": "or" if pending_or else "and",
                        "numeric_value": nombre,
                    }))
                    continue
                # ⚠️ **LE SÉLECTEUR ÉCRIT `=`, LE STOCKAGE NE CONNAÎT QUE `in`.**
                # Choisir un champ dans l'éditeur de domaine produit `('champ', '=',
                # id)` — c'est son défaut pour un `many2one`. Refuser sec rendait le
                # dialogue hostile : on désigne un attribut, et l'enregistrement
                # échoue sans qu'on ait rien fait de faux. `=` et `!=` disent
                # exactement `in` et `not in` sur une valeur unique : on traduit.
                if operator in ("=", "!="):
                    # ⓘ `= False` (« n'est pas défini ») n'a PAS d'équivalent : une
                    # valeur absente n'est pas une valeur à écarter. Une liste vide
                    # tombe alors sur le refus de la ligne vide, qui le dit.
                    if not isinstance(values, list | tuple):
                        values = [values] if values else []
                    values = [v for v in values if v]
                    operator = "in" if operator == "=" else "not in"
                if operator not in ("in", "not in"):
                    raise ValidationError(
                        self.env._(
                            "A configuration condition only supports 'in' and "
                            "'not in', not '%(operator)s'",
                            operator=operator,
                        )
                    )
                prefixe = (
                    self.PRODUCT_FIELD_PREFIX if produits
                    else self.ATTRIBUTE_FIELD_PREFIX
                )
                attribute_id = int(field_name[len(prefixe) :])
                champ = "product_ids" if produits else "value_ids"
                lines.append(
                    (
                        0,
                        0,
                        {
                            "attribute_id": attribute_id,
                            "condition": operator,
                            "operator": "or" if pending_or else "and",
                            champ: [(6, 0, list(values))],
                        },
                    )
                )
        self.domain_line_ids = [(5, 0, 0)] + lines
        return True

    def _facet_data(self):
        """Les pastilles AVEC l'identité de la règle que chacune porte — D-211.

        ⚠️ Un « × » sur une pastille retire **une règle**, pas la condition
        entière. Sans cet identifiant, le seul geste possible serait « tout
        effacer » — et une condition à trois règles se perdrait pour en corriger
        une. C'est le comportement de la barre de recherche (D-211).
        """
        if not self:
            return []
        self.ensure_one()
        lignes = self.domain_line_ids.sorted()
        facettes = []
        for index, (ligne, label) in enumerate(zip(lignes, self._facet_labels())):
            # ⚠️ **LA PASTILLE EST STRUCTURÉE, pas une phrase** : une facette du cœur a
            # un entête, des valeurs séparées par un mot, et sa propre croix — un
            # unique texte ne peut pas rendre ça (D-225).
            designes = ligne.product_ids or ligne.value_ids
            facettes.append({
                "id": ligne.id,
                # ⓘ Le texte plat reste rendu : c'est l'infobulle de la pastille,
                # et ce que lisent les tests d'ordre de lecture.
                "label": label,
                "title": ligne.attribute_id.name or "?",
                "negated": ligne.condition == "not in",
                "values": designes.mapped(
                    "display_name" if ligne.product_ids else "name"
                ),
                # ⚠️ **OU À L'INTÉRIEUR D'UNE PASTILLE** (D-203) — c'est ce que
                # produit `compute_domain`, où une ligne porte plusieurs valeurs.
                "separator": self.env._("or"),
                # ⓘ ET entre pastilles est IMPLICITE, comme dans la barre de
                # recherche : seul un « ou » se dit. Et c'est l'opérateur de la
                # ligne PRÉCÉDENTE qui gouverne la jonction (cf. `_facet_labels`).
                "link": (
                    self.env._("or")
                    if index and lignes[index - 1].operator == "or"
                    else False
                ),
            })
        return facettes

    def _facet_labels(self):
        """Les pastilles, dans l'ordre — une par ligne de condition.

        ⚠️ **L'OPÉRATEUR D'UNE LIGNE GOUVERNE SA JONCTION AVEC LA SUIVANTE**, et
        c'est contre-intuitif. `to_odoo_domain` émet le `|` **avant** la ligne qui
        le porte, en notation préfixe : trois lignes A, B, C dont A est en `or`
        donnent `['|', A, B, C]`, soit **(A OU B) ET C**. Le lien annoncé devant
        la pastille n° 2 est donc l'opérateur de la n° 1.

        ⓘ Je l'avais écrit à l'envers en première intention. Lu ainsi, un `ou`
        s'affichait sur la mauvaise jonction — et deux conditions différentes se
        seraient lues pareil.
        """
        # ⚠️ **PAS DE CONDITION, PAS DE PASTILLE — et surtout pas une erreur.**
        # L'appelant le plus fréquent est une ligne qui n'en porte AUCUNE : un
        # `ensure_one()` sec y levait « Expected singleton », et l'arbre entier
        # tombait à cause des lignes ordinaires.
        if not self:
            return []
        self.ensure_one()
        labels = []
        lignes = self.domain_line_ids.sorted()
        for index, ligne in enumerate(lignes):
            # ⓘ Une feuille « produit » se lit par ses PRODUITS, pas par les
            # valeurs qu'elle résout : c'est ce que son auteur a écrit.
            designes = ligne.product_ids or ligne.value_ids
            valeurs = " / ".join(
                designes.mapped("display_name" if ligne.product_ids else "name")
            )
            if ligne.condition in ligne.NUMERIC_CONDITIONS:
                # ⓘ Une comparaison se lit telle qu'elle s'écrit : « largeur > 4000 ».
                # Rien à traduire — un opérateur n'est pas de la prose.
                libelle = "%s %s %s" % (
                    ligne.attribute_id.name or "?",
                    ligne.condition,
                    ("%g" % ligne.numeric_value),
                )
            else:
                dedans = ligne.condition == "in"
                libelle = "%s %s %s" % (
                    ligne.attribute_id.name or "?",
                    "=" if dedans else "\u2260",
                    valeurs or "?",
                )
            if index:
                precedente = lignes[index - 1]
                lien = (
                    self.env._("or")
                    if precedente.operator == "or"
                    else self.env._("and")
                )
                libelle = "%s %s" % (lien, libelle)
            labels.append(libelle)
        return labels
