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
    # ⓘ **PLUS AUCUN ASSET, et c'est le cœur de ce lot.** Le bouton « Configure » qui
    # vivait ici s'injectait dans les gabarits GÉNÉRIQUES de toutes les listes, kanbans
    # et formulaires du back-office, se cachait en CSS, puis se rallumait en JS quand le
    # modèle était le bon. Mesuré le 2026-09-18 : un clic partait **deux fois**, le
    # gabarit et le mixin ayant chacun branché le leur sur le même bouton.
    #
    # Il est remplacé par `product_configurator_web_3d_mrp`, qui pose un WIDGET sur le
    # seul champ produit — cadré par construction (arbitrage Gerry, 2026-09-19 :
    # *« cela évite la présence inutile de ce bouton »*).
    "demo": ["demo/product_template.xml"],
    "installable": True,
    "auto_install": False,
    "development_status": "Beta",
    "maintainers": ["PCatinean"],
}
