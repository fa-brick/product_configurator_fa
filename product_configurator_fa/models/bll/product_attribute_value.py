"""Ce qu'exécute `product.attribute.value` (BLL, D-541)."""
from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    # ─ LA LIGNE SE REMPLIT SEULE — D-198 ────────────────────────────────────
    #
    # ⚠️ La miniature suit seule (elle est `related`), pas le nom — et `name` est
    # REQUIS : sans ce remplissage, il faut retaper ce qu'on vient de désigner pour
    # pouvoir enregistrer (D-198).
    #
    # ⚠️ Le nom n'est pas ÉCRASÉ s'il a été personnalisé. On ne remplace que le vide
    # ou le nom hérité du produit précédent (lu sur `_origin`, l'enregistrement en
    # base). Sans cette précaution, renommer une valeur puis corriger le produit
    # effacerait le libellé choisi — et un libellé est ce que le client lit.
    @api.onchange("product_id")
    def _onchange_product_id_fills_the_name(self):
        if not self.product_id:
            return
        ancien = (
            self._origin.product_id.display_name if self._origin.product_id else False
        )
        if not self.name or self.name == ancien:
            self.name = self.product_id.display_name

    # ─ DEUX BARRIÈRES, encore (D-080, D-194, D-196) ─────────────────────────
    @api.constrains("product_id")
    def _check_product_only_for_product_type(self):
        for value in self:
            if value.product_id and value.attribute_id.value_type != "product":
                raise ValidationError(
                    self.env._(
                        "Only an attribute whose values designate a Product can "
                        "point at one. Change the attribute's value type, or "
                        "clear the product."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Range le nombre, et pose la séquence — D-081, conditions 2 et 3.

        ⚠️ Sans la séquence, les largeurs s'afficheraient **dans l'ordre où
        elles ont été vendues** : les valeurs se trient par `sequence` puis par
        id, et celles créées à la volée vaudraient toutes zéro. Le nombre
        lui-même fait une séquence.
        """
        for vals in vals_list:
            attribute = self.env["product.attribute"].browse(vals.get("attribute_id"))
            name = vals.get("name")
            if not attribute or not isinstance(name, str):
                continue
            if not attribute._is_numeric_custom():
                continue
            vals["name"] = name = attribute.canonical_custom_value(name)
            if not vals.get("sequence"):
                try:
                    vals["sequence"] = int(round(float(name)))
                except (TypeError, ValueError):
                    pass
        return super().create(vals_list)

    def copy(self, default=None):
        """Add ' (Copy)' in name to prevent attribute
        having same name while copying"""
        if not default:
            default = {}
        default.update({"name": self.name + " (copy)"})
        product = super().copy(default)
        return product

    # ⓘ **`display_value` A DÉMÉNAGÉ** vers `product_attribute_advanced`
    # (D-160), avec le formateur dont il dépend : ce qu'une valeur MONTRE
    # ne dépend que de son format et de son unité, et l'éditeur en a besoin
    # sans le configurateur.
    def init(self):
        """Unicité `(attribut, nom)` EN BASE — D-081, condition 2.

        ⚠️ Aucun verrou applicatif ne remplace celle-ci : « je cherche, sinon je
        crée » laisse passer deux clients simultanés, et le stock se coupe en
        deux. Odoo n'en pose AUCUNE sur ce modèle.

        Deux détails qui ne sont pas des détails :
        · `name` est **traduit**, donc stocké en `jsonb`. L'index porte sur le
          terme source (`name->>'en_US'`) et non sur l'objet entier : sinon
          traduire une valeur en ferait une valeur différente, et le doublon
          repasserait ;
        · `WHERE active is true` — le ménage ARCHIVE (D-082), et une largeur
          archivée ne doit pas empêcher la même largeur de revivre.
        """
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS product_attribute_value_name_unique
            ON %s (attribute_id, (name->>'en_US')) WHERE active is true
            """
            % self._table
        )

    @api.autovacuum
    def _gc_configurator_values(self):
        """Archive les largeurs créées par le configurateur et jamais servies.

        ⚠️ **D-082 est à corriger sur la forme** : elle annonce « toute méthode
        nommée `_gc_*` » — c'était vrai jusqu'aux versions précédentes. En
        Odoo 18, `ir.autovacuum` ne collecte plus par le NOM mais par le
        décorateur `@api.autovacuum` (`ir_autovacuum.py:34`). Une méthode juste
        nommée `_gc_…` ne serait jamais appelée, et **rien ne le dirait**.

        Le critère de D-082 est « créée il y a plus de N jours ET jamais
        employée ». « Jamais employée » se lit ici **n'est portée par aucune
        variante** : puisque rien n'est résolu avant le devis (D-082), une
        valeur sans variante n'a jamais servi à vendre quoi que ce soit. Le
        détour par les lignes de vente, les mouvements de stock et les
        nomenclatures est donc inutile — et il aurait obligé le cœur du module
        à connaître `sale` et `mrp`, qu'il ne dépend pas.

        ⚠️ On ARCHIVE, on ne supprime pas : `product.template.attribute.value`
        référence la valeur en `ondelete='restrict'`, et l'historique doit
        rester lisible.
        """
        days = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("product_configurator_fa.value_gc_days", 90)
        )
        candidates = self.sudo().search(
            [
                ("configurator_generated", "=", True),
                ("create_date", "<", fields.Datetime.now() - timedelta(days=days)),
            ]
        )
        if not candidates:
            return
        ptavs = (
            self.env["product.template.attribute.value"]
            .sudo()
            .with_context(active_test=False)
            .search([("product_attribute_value_id", "in", candidates.ids)])
        )
        served = ptavs.filtered("ptav_product_variant_ids").product_attribute_value_id
        for value in candidates - served:
            for ptav in ptavs.filtered(
                lambda p, value=value: p.product_attribute_value_id == value
            ):
                line = ptav.attribute_line_id
                # Une ligne non personnalisable doit garder au moins une valeur
                # (`_check_valid_values`) : mieux vaut laisser la largeur en
                # place que casser le produit pour faire du ménage.
                if len(line.value_ids) > 1 or line.custom:
                    line.write({"value_ids": [(3, value.id)]})
            value.active = False

    def _purge_designation(self, value_type):
        """Efface ce que la valeur désignait, si le nouveau type l'interdit — D-219.

        ⚠️ Sans purge, basculer de « produit » à « matière » garde les `product_id`
        sur les valeurs, et la garde de D-196 refuse l'enregistrement — sur des
        champs devenus invisibles. Même faute que D-194, un étage plus bas.

        ⓘ Un crochet, parce que `material_id` vit dans le PONT : le cœur ne peut
        pas nommer un champ de l'éditeur (D-075). Chaque module efface ce qu'il a
        posé.
        """
        if value_type != "product":
            self.filtered("product_id").product_id = False

    @api.model
    def get_attribute_value_extra_prices(self, product_tmpl_id, pt_attr_value_ids):
        """Le supplément de chaque valeur sur ce produit — `{id de valeur: montant}`.

        ⚠️ **UNE VALEUR QUI DÉSIGNE UN PRODUIT EST FACTURÉE AU PRIX DE CE PRODUIT**,
        et le montant enregistré est alors ignoré. Ce n'est pas un oubli : c'est la
        fonctionnalité, et `test_04_compute_cfg_price` l'énonce ligne à ligne —
        prix du modèle, plus le `lst_price` du moteur, de la finition, de la boîte
        et de l'option.

        ⚠️ **NE PAS RENDRE LE MONTANT ENREGISTRÉ DÉCISIONNAIRE** (D-199) : MESURÉ sur
        la base de démo, le prix d'une configuration tombait de 35 748 à 25 000, parce
        que les valeurs existantes ne stockent aucun montant.

        ⚠️ Le prix CATALOGUE du composant, jamais celui de la liste de prix : le total
        y passe déjà, et la remise compterait deux fois sur le composant (D-537).
        """
        related_product_av_ids = self.env["product.attribute.value"].search(
            [("id", "in", pt_attr_value_ids.ids), ("product_id", "!=", False)]
        )
        extra_prices = {
            # ⚠️ `sudo` — SANS LUI, TOUTE FICHE PUBLIQUE D'UN PRODUIT CONFIGURABLE
            # RÉPOND 403. Une valeur qui désigne un COMPOSANT (une top plate, un bras)
            # pointe un produit non publié : la règle d'enregistrement le cache au
            # visiteur, et lire son prix ici lève un `AccessError` qui emporte le rendu
            # de la page entière. Mesuré sur le JeNo, produit 50.
            #
            # ⓘ Ce qu'on lit est un PRIX, et il entre dans un total que le visiteur voit
            # de toute façon. Publier le composant serait l'autre issue — mais elle
            # exposerait dans la boutique des pièces qui n'ont pas à s'y vendre.
            # ⓘ `_price_compute` et non `lst_price` : la grille d'un composant à grille
            # n'entre que par lui (D-093).
            av.id: av.product_id.sudo()._price_compute("list_price")[av.product_id.id]
            for av in related_product_av_ids
        }
        remaining_av_ids = pt_attr_value_ids - related_product_av_ids
        pe_lines = self.env["product.template.attribute.value"].search(
            [
                ("product_attribute_value_id", "in", remaining_av_ids.ids),
                ("product_tmpl_id", "=", product_tmpl_id),
            ]
        )
        for line in pe_lines:
            attr_val_id = line.product_attribute_value_id
            if attr_val_id.id not in extra_prices:
                extra_prices[attr_val_id.id] = 0
            extra_prices[attr_val_id.id] += line.price_extra
        return extra_prices

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Use name_search as a domain restriction for the frontend to show
        only values set on the product template taking all the configuration
        restrictions into account.

        TODO: This only works when activating the selection not when typing
        """
        product_tmpl_id = self.env.context.get("_cfg_product_tmpl_id")
        if product_tmpl_id:
            # TODO: Avoiding browse here could be a good performance enhancer
            product_tmpl = self.env["product.template"].browse(product_tmpl_id)
            tmpl_vals = product_tmpl.attribute_line_ids.mapped("value_ids")
            attr_restrict_ids = []
            preset_val_ids = []
            new_args = []
            for arg in args:
                # Restrict values only to value_ids set on product_template
                if arg[0] == "id" and arg[1] == "not in":
                    preset_val_ids = arg[2]
                    # TODO: Check if all values are available for configuration
                else:
                    new_args.append(arg)
            val_ids = set(tmpl_vals.ids)
            if preset_val_ids:
                val_ids -= set(arg[2])
            val_ids = self.env["product.config.session"].values_available(
                val_ids, preset_val_ids, product_tmpl_id=product_tmpl_id
            )
            new_args.append(("id", "in", val_ids))
            mono_tmpl_lines = product_tmpl.attribute_line_ids.filtered(
                lambda line: not line.multi
            )
            for line in mono_tmpl_lines:
                line_val_ids = set(line.mapped("value_ids").ids)
                if line_val_ids & set(preset_val_ids):
                    attr_restrict_ids.append(line.attribute_id.id)
            if attr_restrict_ids:
                new_args.append(("attribute_id", "not in", attr_restrict_ids))
            args = new_args
        res = super().name_search(name=name, args=args, operator=operator, limit=limit)
        return res
    # TODO: Prevent unlinking custom options by overriding unlink
    # _sql_constraints = [
    #    ('unique_custom', 'unique(id,allow_custom_value)',
    #    'Only one custom value per dimension type is allowed')
    # ]
