# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Product Configurator - Variant Grid (fa-brick)",
    "version": "18.0.1.0.0",
    "category": "Generic Modules/Sale",
    "summary": "Shows the configurator's variant name next to the variant grid choice",
    "author": "fa-brick",
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    # ⚠️ UN PONT en `auto_install` : faire dépendre le configurateur de `sale_product_matrix`
    # imposerait la grille des variantes à tout concepteur (D-399, option B).
    # ⓘ Sans la grille, le Nom de variante reste simplement en bas de l'onglet.
    "depends": ["product_configurator_fa", "sale_product_matrix"],
    "data": ["views/product_view.xml"],
    "installable": True,
    "auto_install": True,
    "development_status": "Beta",
}
