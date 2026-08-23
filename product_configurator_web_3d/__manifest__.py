{
    "name": "Product Configurator 3D Web (fa-brick)",
    "version": "18.0.0.1.0",
    "category": "Sales/Sales",
    "summary": "3D configurator interface — the shell the views hang from",
    "author": "fa-brick",
    # AGPL-3 comme le cœur du configurateur : ce module en dépend, et le SENS de
    # la dépendance décide de la licence (D-075). L'éditeur reste LGPL-3 et ne
    # dépend de rien — c'est ce que cette séparation protège.
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    "depends": ["product_configurator_fa", "product_editor"],
    "data": [
        "views/product_view.xml",
    ],
    "installable": True,
    "auto_install": False,
}
