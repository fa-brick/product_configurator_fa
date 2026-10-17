# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Product Configurator Manufacturing (fa-brick)",
    "version": "18.0.1.1.0",
    "category": "Manufacturing",
    "summary": "BOM Support for configurable products",
    "author": "Pledra, Odoo Community Association (OCA), fa-brick",
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    "depends": ["mrp", "mrp_account", "product_configurator_fa"],
    "data": [
        "data/menu_product.xml",
        "data/ir_cron_data.xml",
        "views/mrp_view.xml",
        "security/configurator_security.xml",
        "security/ir.model.access.csv",
    ],
    # ⚠️ AUCUN ASSET : un bouton « Configure » injecté dans les gabarits GÉNÉRIQUES du
    # back-office partait DEUX fois au clic (gabarit et mixin branchés sur le même bouton).
    # ⓘ Le configurateur s'ouvre par le WIDGET de `product_configurator_web_3d_mrp`, posé sur
    # le seul champ produit.
    "demo": ["demo/product_template.xml"],
    "installable": True,
    "auto_install": False,
    "development_status": "Beta",
    "maintainers": ["PCatinean"],
}
