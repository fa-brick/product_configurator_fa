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
    "installable": True,
    "auto_install": False,
}
