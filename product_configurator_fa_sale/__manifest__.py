# Copyright (C) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Product Configurator Sale (fa-brick)",
    "version": "18.0.1.0.1",
    "category": "Generic Modules/Sale",
    "summary": "Product configuration interface modules for Sale",
    "author": "Pledra, Odoo Community Association (OCA), fa-brick",
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    "depends": ["sale_management", "product_configurator_fa", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/menu_product.xml",
        "views/sale_view.xml",
    ],
    "demo": ["demo/res_partner_demo.xml"],
    "installable": True,
    "auto_install": True,
    "development_status": "Beta",
    "maintainers": ["PCatinean"],
}
