"""Le `config_ok` de la ligne de devis part — la vue du pont 3D s'y ancrait.

⚠️ La vue de `product_configurator_web_3d_sale`, telle qu'elle est en base, vise ce champ :
sans ce retrait, sa validation fait échouer la mise à jour (L-164).
ⓘ Le pont la recrée en se chargeant, ancrée sur `config_session_id` (D-497).
"""
import logging

_logger = logging.getLogger(__name__)

#: La vue du pont qui s'ancrait sur `config_ok`.
XMLID = "product_configurator_web_3d_sale.sale_order_form_web3d"


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
