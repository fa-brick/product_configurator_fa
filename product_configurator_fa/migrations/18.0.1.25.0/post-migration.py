# -*- coding: utf-8 -*-
"""`custom_type` cède la source de vérité à `nature`.

⚠️ **Le format ne disparaît pas, il change de rang.** Il décrit désormais COMMENT une
réponse se saisit — entier ou décimal, et cette précision-là n'existe que dans ce module.
La NATURE, elle, dit de quoi la question parle, et vit dans `product_attribute_advanced`
parce que l'éditeur 3D en a besoin sans pouvoir dépendre d'ici (D-075).

ⓘ Cette reprise est FRANCHE, sans les précautions qu'une base vivante imposerait : Gerry
a tranché le 2026-09-01 — *« la casse des données n'est pas gênante, on reste sur une base
de test »*.
"""
import logging

_logger = logging.getLogger(__name__)

#: ⚠️ `binary` → `attachment`, et cette ligne a failli manquer. La mesure disait
#: qu'aucun attribut ne porte ce format ; le CODE, lui, s'en sert — un client
#: téléverse un fichier comme réponse. Une donnée inutilisée n'est pas une
#: capacité absente.
TO_NATURE = {
    "char": "text",
    "integer": "number",
    "float": "number",
    "binary": "attachment",
}


def migrate(cr, version):
    if not version:
        return

    for custom_type, nature in TO_NATURE.items():
        cr.execute(
            "UPDATE product_attribute SET nature = %s WHERE custom_type = %s",
            (nature, custom_type),
        )
        if cr.rowcount:
            _logger.info("%s attribut(s) « %s » deviennent de nature « %s ».",
                         cr.rowcount, custom_type, nature)

    # ⓘ Un attribut SANS format garde la nature par défaut, `text` — la seule qui
    # n'ouvre aucun rôle. Sur la base de travail c'est le cas de dix attributs sur
    # treize : leur nature se saisira à la main, en connaissance de cause, plutôt
    # que d'être devinée depuis la forme de leurs valeurs.
    cr.execute("SELECT count(*) FROM product_attribute WHERE custom_type IS NULL")
    orphans = cr.fetchone()[0]
    if orphans:
        _logger.info(
            "%s attribut(s) sans format restent de nature « text » : à qualifier à la main.",
            orphans,
        )
