{
    "name": "Product Configurator 3D — Dimensioned drawings on quotations (fa-brick)",
    "version": "18.0.0.1.0",
    "category": "Sales/Sales",
    "summary": "Join the dimensioned drawing of each configured product to its quotation PDF and portal",
    "author": "fa-brick",
    # AGPL-3, comme le pont qu'il étend (D-075).
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    # ⓘ Un module À PART : le modèle de document (product_editor_document) et le devis du configurateur
    # existent chacun sans l'autre ; ce pont les réunit (W-118, lot 6).
    "depends": ["product_configurator_web_3d_sale", "product_editor_document"],
    "data": [
        "report/drawing_report.xml",
        "views/sale_portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "product_configurator_web_3d_sale_drawing/static/src/drawing_portal.scss",
        ],
    },
    "installable": True,
    # ⓘ Les deux installés, le plan sur le devis l'est aussi.
    "auto_install": True,
}
