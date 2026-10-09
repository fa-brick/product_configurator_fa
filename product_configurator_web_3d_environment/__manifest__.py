{
    "name": "Product Configurator 3D — Environments (fa-brick)",
    "version": "18.0.0.1.0",
    "category": "Website/Website",
    "summary": "Place configurable products in the bays of an environment, and configure them there",
    "author": "fa-brick",
    # AGPL-3 comme tout ce qui dépend du cœur du configurateur (D-075) ; l'environnement, lui,
    # reste en LGPL dans `product_3Dmodel` (M-4) : ce pont est le seul endroit où ils se joignent.
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    "depends": ["product_configurator_web_3d", "product_editor_environment"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_environment_views.xml",
    ],
    "assets": {
        # ⓘ Le même éditeur au site et au back-office (E-5) : la pose se branche des deux côtés.
        "web.assets_backend": [
            "product_configurator_web_3d_environment/static/src/environment_place.scss",
            "product_configurator_web_3d_environment/static/src/environment_place.xml",
            "product_configurator_web_3d_environment/static/src/environment_place.js",
        ],
        "web.assets_frontend": [
            "product_configurator_web_3d_environment/static/src/environment_place.scss",
            "product_configurator_web_3d_environment/static/src/environment_place.xml",
            "product_configurator_web_3d_environment/static/src/environment_place.js",
        ],
    },
    "installable": True,
    # ⓘ Les deux parents installés, la pose dans un environnement l'est aussi : sans ce pont, le
    # « + » d'une baie ne s'affiche pas (`_editor_can_place`).
    "auto_install": True,
}
