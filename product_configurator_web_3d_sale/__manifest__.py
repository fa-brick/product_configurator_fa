{
    "name": "Product Configurator 3D — Quotation lines (fa-brick)",
    "version": "18.0.0.1.0",
    "category": "Sales/Sales",
    "summary": "Configure or resume a configuration from a quotation line, in 3D",
    "author": "fa-brick",
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    # ⚠️ CE PONT N'EXIGE PAS L'E-COMMERCE — et c'est sa raison d'être.
    # Un commercial interne configure depuis un devis sur une base sans
    # boutique ; `product_configurator_web_sale` (la boutique) est un TROISIÈME
    # chemin, indépendant de celui-ci. Les deux ouvrent la même page.
    "depends": ["product_configurator_web_3d", "product_configurator_fa_sale"],
    "installable": True,
    "auto_install": False,
}
