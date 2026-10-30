{
    "name": "Product Configurator 3D — Wishlist (fa-brick)",
    "version": "18.0.0.1.0",
    "category": "Website/Website",
    "summary": "A configured product in the wishlist shows its answers and reopens the configurator",
    "author": "fa-brick",
    # AGPL-3 comme tout ce qui dépend du cœur du configurateur (D-075).
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    # ⚠️ Un pont, pour ne pas imposer la liste de souhaits à toute boutique qui configure (D-557).
    "depends": ["product_configurator_web_sale", "website_sale_wishlist"],
    "data": [
        "views/templates.xml",
    ],
    "installable": True,
    "auto_install": True,
}
