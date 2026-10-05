# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Product Configurator - Variant Grid (fa-brick)",
    "version": "18.0.1.0.0",
    "category": "Generic Modules/Sale",
    "summary": "Shows the configurator's variant name next to the variant grid choice",
    "author": "fa-brick",
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    # ⓘ UN PONT, et rien d'autre (D-399, Gerry 2026-10-05, option B). « Sélection des
    # variantes de vente » vient de `sale_product_matrix` (la saisie des variantes en
    # grille, une option des Ventes) ; le configurateur n'en dépend pas, et ne doit pas en
    # dépendre : la grille est un choix de vente propre à chaque concepteur. Ce module ne
    # s'installe donc QUE là où les deux sont déjà présents (`auto_install`), et n'impose
    # rien ailleurs — le Nom de variante y reste simplement en bas de l'onglet.
    "depends": ["product_configurator_fa", "sale_product_matrix"],
    "data": ["views/product_view.xml"],
    "installable": True,
    "auto_install": True,
    "development_status": "Beta",
}
