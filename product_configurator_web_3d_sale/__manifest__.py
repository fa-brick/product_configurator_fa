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
    "data": [
        "views/sale_view.xml",
    ],
    "assets": {
        # ══ LE MÊME CONFIGURATEUR, DANS LE DEVIS — D-259 ═══════════════════════
        #
        # ⓘ **Rien du viewer n'est listé ici** : `product_editor` met déjà ses 65
        # fichiers dans `web.assets_backend` (vérifié le 2026-09-06 en comparant
        # les deux listes du manifeste de l'éditeur). Le back-office porte donc
        # la scène 3D depuis toujours — c'est le FRONT qui avait dû la recevoir.
        #
        # ⚠️ L'ordre reste significatif ([[L-001]]) : l'état, puis la page qu'il
        # nourrit, puis le dialogue qui la monte, puis le correctif qui l'ouvre.
        # ⓘ **La PAGE n'est plus listée ici** (2026-09-07) : elle est déclarée par
        # `product_configurator_web_3d`, qui la possède et l'ouvre lui-même en
        # dialogue depuis une fiche produit (D-262). La lister deux fois la
        # chargerait deux fois.
        "web.assets_backend": [
            "product_configurator_web_3d_sale/static/src/configurator_dialog.scss",
            "product_configurator_web_3d_sale/static/src/configurator_dialog.xml",
            "product_configurator_web_3d_sale/static/src/configurator_dialog.js",
            "product_configurator_web_3d_sale/static/src/sale_product_field_patch.js",
        ],
    },
    "installable": True,
    "auto_install": False,
}
