"""L'arbre remplace la liste — la vue de colonne du pont n'a plus de cible.

⚠️ **UNE VUE ENREGISTRÉE PEUT VISER UN NŒUD QUE L'ON VIENT DE RETIRER.** Le pont
3D ajoutait sa colonne « Vue 3d » *après* la condition, dans la liste du cœur.
Cette condition déménage vers l'onglet configurateur — et la vue du pont, telle
qu'elle est **en base**, vise toujours l'ancien emplacement.

Or Odoo met à jour les modules dans l'ordre des dépendances : ce module d'abord,
le pont ensuite. À l'instant où les vues d'ici sont rechargées, celle du pont est
encore l'ancienne, et sa validation échoue :

    Element '<xpath expr="//field[@name='attribute_line_ids']/list/
    field[@name='visibility_domain_id']">' cannot be located in parent view

⇒ **Mesuré, et bloquant** : la mise à jour échoue avant même d'arriver au pont.
On retire donc la vue périmée ici ; le pont la recrée en se chargeant, avec son
`xpath` neuf. Rien n'est perdu — une vue est reconstruite depuis son fichier.

ⓘ Sans ce geste, la seule issue serait de désinstaller le pont avant de mettre à
jour. Personne ne peut le deviner devant le message ci-dessus.
"""
import logging

_logger = logging.getLogger(__name__)

#: La vue du pont qui visait l'ancien emplacement.
XMLID = "product_configurator_web_3d.product_template_form_view_3d"


def migrate(cr, version):
    module, name = XMLID.split(".")
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s",
        (module, name),
    )
    ligne = cr.fetchone()
    if not ligne:
        _logger.info("La vue %s n'existe pas ici : rien à retirer.", XMLID)
        return
    cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (ligne[0],))
    cr.execute(
        "DELETE FROM ir_model_data WHERE module = %s AND name = %s", (module, name)
    )
    _logger.info("Vue périmée %s retirée : le pont la recréera.", XMLID)
