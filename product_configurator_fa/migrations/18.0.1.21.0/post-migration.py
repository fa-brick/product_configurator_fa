"""Les listes dynamiques déjà en base se rétractent une fois.

⚠️ **Constat de Gerry à l'écran (2026-08-29)** : *« j'ai un résultat, et
plusieurs produits dans la liste »*. La matérialisation (D-222) ajoutait sans
jamais retirer : chaque essai de filtre laissait ses valeurs derrière lui, et la
liste finissait par contredire le compteur qui l'annonçait.

Le code se rétracte désormais à chaque écriture du filtre — mais **les listes
déjà accumulées ne bougeraient qu'au prochain enregistrement**, et rien ne dit à
l'utilisateur qu'il doit en provoquer un. D'où ce passage unique.

ⓘ Il n'invente rien : il rejoue exactement le geste du code, lequel épargne les
valeurs écrites à la main, celles retenues sur un produit, et celles qu'une
condition désigne (D-228).
"""
import logging

_logger = logging.getLogger("_pcfa_migration")


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    attributs = env["product.attribute"].search([("dynamic_values", "=", True)])
    if not attributs:
        return
    retires = 0
    for attribut in attributs:
        avant = len(attribut.value_ids)
        attribut._materialise_proposed_values()
        retires += max(0, avant - len(attribut.value_ids))
    _logger.info(
        "%s liste(s) dynamique(s) remise(s) d'aplomb : %s valeur(s) retirée(s).",
        len(attributs),
        retires,
    )
