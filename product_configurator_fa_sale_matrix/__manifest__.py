# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Product Configurator - Variant Grid (fa-brick)",
    "version": "18.0.1.1.0",
    "category": "Generic Modules/Sale",
    "summary": "Empty: kept only so that databases where it is installed can uninstall it",
    "author": "fa-brick",
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    # ⚠️ VIDE depuis le retrait du nom de variante Mako, qu'il déplaçait (D-497) : à
    # désinstaller là où il l'est, puis à supprimer du dépôt.
    # ⚠️ Plus d'`auto_install` : il s'installerait de lui-même sur toute base neuve avec
    # la grille des variantes.
    "depends": ["product_configurator_fa", "sale_product_matrix"],
    "data": [],
    "installable": True,
    "auto_install": False,
    "development_status": "Beta",
}
