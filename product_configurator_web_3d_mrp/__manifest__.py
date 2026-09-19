# Copyright 2026 fa-brick
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Configurateur 3D — Fabrication",
    "version": "18.0.1.0.0",
    "category": "Manufacturing",
    "summary": "Choisir un produit configurable sur un ordre de fabrication "
               "ouvre le configurateur 3D",
    "author": "fa-brick",
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    # ⓘ Le PONT, et rien d'autre : la fabrication d'un côté, le configurateur 3D de
    # l'autre. C'est le pendant exact de `product_configurator_web_3d_sale`, et la
    # raison pour laquelle la fabrication n'a pas à dépendre de la vente.
    "depends": ["product_configurator_fa_mrp", "product_configurator_web_3d"],
    # ⓘ **AUCUN modèle Python, et c'est le signe que ce pont est au bon endroit.**
    # Odoo donne déjà `product_tmpl_id` sur un ordre de fabrication, et
    # `product_configurator_fa_mrp` donne `config_ok` et `config_session_id`. Tout ce
    # qu'il restait à faire était de brancher le geste.
    "data": ["views/mrp_production_views.xml"],
    "assets": {
        "web.assets_backend": [
            # ⚠️ Rien du dialogue ni de la page ici : `product_configurator_web_3d` les
            # déclare déjà, et les lister deux fois les chargerait deux fois.
            "product_configurator_web_3d_mrp/static/src/mrp_product_field.js",
        ],
    },
    "installable": True,
    "auto_install": True,
}
