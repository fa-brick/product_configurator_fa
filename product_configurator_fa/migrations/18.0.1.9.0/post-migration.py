"""L'appartenance à une étape devient un ORDRE — B1, D-202.

⚠️ **Ce qui était coché doit devenir une position.** L'étape était un contenant :
`config_step_line.attribute_line_ids`, un Many2many explicite. Elle devient un
séparateur — ce qui suit lui appartient jusqu'au suivant. La liste cochée n'a
donc plus de sens en soi ; il faut la **traduire** en un ordre, sans quoi les
étapes existantes se retrouveraient vides du jour au lendemain.

⚠️ **On lit l'ANCIENNE table de relation, qui existe encore.** Odoo ne supprime
jamais une table devenue orpheline quand un champ passe de stocké à calculé : le
Many2many n'est plus déclaré, mais `config_step_line_attr_id_rel` est toujours
là, avec ses lignes. C'est la seule source de l'appartenance d'avant.

**Ce que la traduction décide, et qu'il faut assumer :**

· les lignes qui n'appartenaient à AUCUNE étape passent en TÊTE — avec un
  séparateur, tout ce qui suit une étape lui appartient : les laisser à leur
  place les aurait absorbées dans l'étape précédente ;
· une ligne cochée dans DEUX étapes va à la première — le contenant le
  permettait, le séparateur non ;
· la première ligne de chaque étape en devient l'ouvreuse.

Mesuré avant d'écrire : `fabk18` porte **0** ligne d'étape, la base de démo 5
(8 appartenances). La reprise est donc petite — mais elle doit être juste.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT to_regclass('config_step_line_attr_id_rel')")
    if not cr.fetchone()[0]:
        _logger.info("Aucune table d'appartenance : rien à reprendre.")
        return

    # Les étapes, par produit, dans leur ordre d'alors.
    cr.execute(
        """
        SELECT sl.product_tmpl_id, sl.id, sl.config_step_id
          FROM product_config_step_line sl
         ORDER BY sl.product_tmpl_id, sl.sequence, sl.config_step_id, sl.id
        """
    )
    etapes_par_produit = {}
    for tmpl_id, step_line_id, step_id in cr.fetchall():
        etapes_par_produit.setdefault(tmpl_id, []).append((step_line_id, step_id))
    if not etapes_par_produit:
        _logger.info("Aucune étape déclarée : rien à reprendre.")
        return

    reordonnes = marques = 0
    for tmpl_id, etapes in etapes_par_produit.items():
        # Toutes les lignes du produit, dans l'ordre qu'elles avaient.
        cr.execute(
            """
            SELECT id FROM product_template_attribute_line
             WHERE product_tmpl_id = %s ORDER BY sequence, id
            """,
            (tmpl_id,),
        )
        toutes = [row[0] for row in cr.fetchall()]

        # L'appartenance d'alors, première étape gagnante.
        appartenance = {}
        for step_line_id, _step_id in etapes:
            cr.execute(
                "SELECT attr_id FROM config_step_line_attr_id_rel WHERE cfg_line_id = %s",
                (step_line_id,),
            )
            for (line_id,) in cr.fetchall():
                appartenance.setdefault(line_id, step_line_id)

        # Les orphelines d'abord, puis chaque étape avec les siennes.
        nouvel_ordre = [l for l in toutes if l not in appartenance]
        ouvreuses = {}
        for step_line_id, step_id in etapes:
            membres = [l for l in toutes if appartenance.get(l) == step_line_id]
            if membres:
                ouvreuses[membres[0]] = step_id
            nouvel_ordre.extend(membres)

        for rang, line_id in enumerate(nouvel_ordre, start=1):
            cr.execute(
                """
                UPDATE product_template_attribute_line
                   SET sequence = %s, config_step_id = %s
                 WHERE id = %s
                """,
                (rang * 10, ouvreuses.get(line_id), line_id),
            )
            reordonnes += 1
        marques += len(ouvreuses)

    # ⚠️ LE RANG DE L'ÉTAPE DOIT ÊTRE ÉCRIT ICI AUSSI. Il est « calculé et stocké »,
    # donc recalculé par l'ORM — mais cette migration écrit en SQL, et le SQL ne
    # déclenche aucun calcul. Sans ces lignes, toutes les étapes gardent le rang par
    # défaut (10) et `_order` les range par identifiant : constaté à l'écran sur la
    # base de démo, les cinq étapes à `sequence=10`.
    cr.execute(
        """
        UPDATE product_config_step_line sl
           SET sequence = COALESCE(
                   (SELECT MIN(l.sequence)
                      FROM product_template_attribute_line l
                     WHERE l.product_tmpl_id = sl.product_tmpl_id
                       AND l.config_step_id = sl.config_step_id),
                   9999)
        """
    )

    _logger.info(
        "Étapes reprises : %s ligne(s) réordonnée(s), %s ouvreuse(s) marquée(s), "
        "%s rang(s) d'étape recalculé(s).",
        reordonnes,
        marques,
        cr.rowcount,
    )
