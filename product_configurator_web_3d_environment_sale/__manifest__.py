{
    "name": "Product Configurator 3D — Environment montage and quotation (fa-brick)",
    "version": "18.0.0.1.0",
    "category": "Sales/Sales",
    "summary": "The montage of an environment belongs to a quotation: ask for it from the environment",
    "author": "fa-brick",
    # AGPL-3, comme le pont qu'il étend (D-075).
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    # ⓘ Un module À PART plutôt qu'une dépendance de plus au pont des environnements : ajouter la
    # vente aux dépendances d'un module déjà installé ne l'installe pas au `-u` (D-426).
    "depends": ["product_configurator_web_3d_environment", "product_configurator_web_3d_sale"],
    "data": [
        "views/sale_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "product_configurator_web_3d_environment_sale/static/src/environment_quote.xml",
            "product_configurator_web_3d_environment_sale/static/src/environment_quote.js",
        ],
        "web.assets_frontend": [
            "product_configurator_web_3d_environment_sale/static/src/environment_quote.xml",
            "product_configurator_web_3d_environment_sale/static/src/environment_quote.js",
        ],
    },
    "installable": True,
    # ⓘ Le pont des environnements et la vente du configurateur installés, le montage par devis l'est aussi.
    "auto_install": True,
}
