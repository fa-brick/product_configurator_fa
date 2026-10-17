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
        # fichiers dans `web.assets_backend` (D-259).
        #
        # ⚠️ L'ordre reste significatif ([[L-001]]) : l'état, puis la page qu'il
        # nourrit, puis le dialogue qui la monte, puis le correctif qui l'ouvre.
        # ⚠️ Ne pas lister la PAGE ici : `product_configurator_web_3d` la déclare déjà,
        # et la lister deux fois la chargerait deux fois (D-262).
        "web.assets_backend": [
            # ⓘ Le DIALOGUE est déclaré par `product_configurator_web_3d` : l'ordre de
            # fabrication en a le même besoin que le devis.
            "product_configurator_web_3d_sale/static/src/sale_product_field_patch.js",
        ],
    },
    "installable": True,
    "auto_install": False,
}
