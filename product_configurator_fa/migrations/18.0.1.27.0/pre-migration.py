"""L'assistant OCA et le nom de variante Mako partent — leurs vues restent en base.

⚠️ Une vue retirée de son fichier n'est balayée qu'à la FIN de la mise à jour : avant, la
validation des vues voisines la relit et bute sur un champ retiré (L-164, L-603).
⚠️ La vue de `product_configurator_fa_sale_matrix` vise un groupe retiré d'ici, et seul
l'amont s'exécute à temps (L-164).
ⓘ Rien n'est perdu : une vue se reconstruit depuis son fichier, et celles-ci n'y sont plus
(D-497).
"""
import logging

_logger = logging.getLogger(__name__)

#: Les vues que les sources ne définissent plus, et qui citent un champ ou un groupe retiré.
XMLIDS = [
    "product_configurator_fa.product_template_variant_name_bottom",
    "product_configurator_fa.product_variant_easy_edit_view_inherit",
    "product_configurator_fa.product_configurator_fa_form",
    "product_configurator_fa_sale_matrix.product_template_variant_name_beside_grid",
]


def migrate(cr, version):
    for xmlid in XMLIDS:
        module, name = xmlid.split(".")
        cr.execute(
            "SELECT res_id FROM ir_model_data "
            "WHERE module = %s AND name = %s AND model = 'ir.ui.view'",
            (module, name),
        )
        ligne = cr.fetchone()
        if not ligne:
            _logger.info("La vue %s n'existe pas ici : rien à retirer.", xmlid)
            continue
        cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (ligne[0],))
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s", (module, name)
        )
        _logger.info("Vue périmée %s retirée.", xmlid)
