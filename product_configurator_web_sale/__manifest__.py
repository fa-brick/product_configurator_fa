{
    "name": "Product Configurator 3D — Shop entry (fa-brick)",
    "version": "18.0.0.1.0",
    "category": "Website/Website",
    "summary": "On the shop, a configurable product is CONFIGURED, not added to the cart",
    "author": "fa-brick",
    # AGPL-3 comme tout ce qui dépend du cœur du configurateur (D-075).
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    # ⚠️ CE PONT EXISTE POUR NE PAS IMPOSER `website_sale` À LA PAGE PUBLIQUE.
    # `product_configurator_web_3d` sert aussi un lien reçu par courriel, sur une
    # base sans boutique : lui ajouter `website_sale` obligerait à installer tout
    # l'e-commerce pour ouvrir une configuration. La boutique est un POINT
    # D'ENTRÉE de plus, pas une dépendance de la page.
    "depends": ["product_configurator_web_3d", "website_sale"],
    "data": [
        "views/templates.xml",
    ],
    "assets": {
        # ⓘ Rien du moteur ici : il est DÉJÀ dans `web.assets_frontend`, donc sur
        # toute page du site — mesuré le 2026-09-06, c'est le même fichier de
        # 2 965 Kio que sert la page du configurateur. Le clic n'a donc rien à
        # télécharger ; ce qui reste à gagner est du CALCUL, et c'est l'objet de
        # ce composant.
        "web.assets_frontend": [
            "product_configurator_web_sale/static/src/overlay/configurator_overlay.scss",
            "product_configurator_web_sale/static/src/overlay/configurator_overlay.xml",
            "product_configurator_web_sale/static/src/overlay/configurator_overlay.js",
        ],
    },
    "installable": True,
    "auto_install": False,
}
