"""L'assistant OCA quitte le devis — et sa vue de MASQUAGE reste en base.

⚠️ **LE MÊME PIÈGE QU'EN 18.0.1.12.0, DANS L'AUTRE SENS.** Là-bas une vue aval
visait un nœud déplacé ; ici elle vise deux nœuds **supprimés**. Les boutons
« Configure Product » et la roue dentée sont partis de ce module (arbitrage
Gerry, 2026-09-19 : *« pour moi le wizard est mort »*), et la vue qui ne servait
qu'à les cacher a été supprimée de ses sources en même temps.

Mais une vue supprimée d'un fichier ne disparaît pas de la base au chargement :
Odoo balaie les enregistrements devenus orphelins à la **fin** de la mise à jour,
dans `_process_end`. Or ici le chargement meurt **avant** d'y arriver :

    Element '<xpath expr="//button[@name='action_config_start']">' cannot be
    located in parent view
      name: sale.order.form.web3d.obsolete   parent: sale.order.form.config

⇒ **Mesuré, et bloquant** : la validation échoue, donc le ménage qui aurait
effacé l'orphelin ne s'exécute jamais, et chaque relance rejoue le même échec.
Un serveur neuf tombe exactement comme l'ancien — le registre ne charge plus du
tout, `/web/health` compris. Rien ne se répare tout seul.

ⓘ **Pourquoi ICI et non dans le module qui la possède.** `product_configurator_
web_3d_sale` charge APRÈS nous, puisqu'il dépend de nous. Quand nos vues sont
rechargées, la sienne est encore l'ancienne. Seul l'amont peut agir à temps.

ⓘ **Rien n'est perdu.** Cette vue ne portait aucune information : deux `xpath`
posant `invisible="1"` sur des boutons qui n'existent plus.
"""
import logging

_logger = logging.getLogger(__name__)

#: La vue aval qui masquait les deux boutons de l'assistant.
XMLID = "product_configurator_web_3d_sale.sale_order_form_web3d_obsolete"


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
    _logger.info("Vue périmée %s retirée : elle n'a plus rien à masquer.", XMLID)
