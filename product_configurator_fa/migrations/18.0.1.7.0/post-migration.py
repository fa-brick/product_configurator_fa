"""Le catalogue de formats se resserre — ce qui reste en base doit suivre.

⚠️ **Une valeur retirée d'un `Selection` ne disparaît PAS de la base.** La colonne
est un `varchar` : la ligne garde `color`, la vue l'affiche vide, et le premier
enregistrement l'efface en silence. Pire, la contrainte sur l'unité se lèverait
sur un format que l'utilisateur ne voit plus.

Mesuré sur `fabk18` avant d'écrire ceci : un seul attribut concerné — « Brand »,
en `color`, sans ajout client et sans une seule valeur. Le nettoyage est donc
sans perte ici, mais il ne peut pas se contenter de ce constat : une autre base
peut en porter d'autres.

Voir D-195 (arbitrage de Gerry, 2026-08-28).
"""
import logging

_logger = logging.getLogger(__name__)

#: Ce que le `Selection` accepte désormais (`CUSTOM_TYPES` du modèle).
#
# ⚠️ `binary` EN FAIT PARTIE. Il avait été retiré de la liste le 2026-08-28 sur une
# affirmation fausse de ma part — « une pièce jointe n'est pas une valeur » —, alors
# que le client joint bel et bien un fichier comme valeur personnalisée et que sept
# tests du module l'exercent. Cette migration est corrigée AVANT d'atteindre une
# base qui en porterait : elle n'a tourné que sur les bases de travail, où aucune
# valeur n'était en `binary` (mesuré).
KEPT = ("char", "integer", "float", "binary")
#: Les formats qu'une unité peut qualifier (`NUMERIC_TYPES`).
NUMERIC = ("integer", "float")


def migrate(cr, version):
    # ⓘ Les formats abandonnés décrivaient des widgets de saisie, pas des façons
    # de lire un libellé. Aucun ne se traduit dans les trois restants : `binary`
    # n'est pas une valeur, `date` n'a jamais désigné une caractéristique. On les
    # efface plutôt que de les tordre en `char`, ce qui inventerait une lecture.
    cr.execute(
        "UPDATE product_attribute SET custom_type = NULL "
        "WHERE custom_type IS NOT NULL AND custom_type NOT IN %s",
        (KEPT,),
    )
    if cr.rowcount:
        _logger.info("%s attribut(s) portaient un format abandonné : effacé.", cr.rowcount)

    # ⚠️ Une unité sur un format non numérique devient irrecevable pour la
    # contrainte. La laisser rendrait l'attribut INENREGISTRABLE, sur un champ
    # que la vue masque désormais.
    cr.execute(
        "UPDATE product_attribute SET uom_id = NULL "
        "WHERE uom_id IS NOT NULL AND (custom_type IS NULL OR custom_type NOT IN %s)",
        (NUMERIC,),
    )
    if cr.rowcount:
        _logger.info("%s attribut(s) portaient une unité sans nombre : effacée.", cr.rowcount)
