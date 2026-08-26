{
    "name": "Product Configurator 3D Web (fa-brick)",
    "version": "18.0.0.3.0",
    "category": "Sales/Sales",
    "summary": "3D configurator interface — public routes, 3D viewer, views",
    "author": "fa-brick",
    # AGPL-3 comme le cœur du configurateur : ce module en dépend, et le SENS de
    # la dépendance décide de la licence (D-075). L'éditeur reste LGPL-3 et ne
    # dépend de rien — c'est ce que cette séparation protège.
    "license": "AGPL-3",
    "website": "https://github.com/fa-brick/product_configurator_fa",
    "depends": ["product_configurator_fa", "product_editor"],
    "data": [
        "views/product_view.xml",
        "views/configurator_page.xml",
    ],
    "assets": {
        # ══ LA PAGE PUBLIQUE A BESOIN DU VIEWER, PAS DE L'ÉDITEUR ══════════════
        #
        # ⚠️ C'est le blocage n° 2 du lot 6, relevé le 2026-08-23 : les assets de
        # `product_editor` étaient TOUS back-office, et le montage « pleine page depuis le
        # site » demande le moteur et la vue 3D côté client.
        #
        # Le sous-bundle `product_editor._viewer3d` est la FERMETURE des imports du viewer
        # — ni sidebar, ni dialogues, ni widgets de champ, ni action de client web. Un
        # garde-fou côté éditeur la recalcule et refuse toute dérive : ajouter un import au
        # viewer sans l'y déclarer casserait cette page-ci, et elle seule.
        #
        # ⓘ Rien à lister ici : `include` évite d'entretenir une seconde liste, qui
        # divergerait (doc Odoo 18 « assets », directive `include`).
        "web.assets_frontend": [
            ("include", "product_editor._viewer3d"),
            # La PAGE elle-même — après le viewer qu'elle monte et la projection qu'elle
            # appelle : l'ordre d'un bundle est significatif (L-001 côté éditeur).
            "product_configurator_web_3d/static/src/configurator_state.js",
            "product_configurator_web_3d/static/src/page/configurator_page.scss",
            "product_configurator_web_3d/static/src/page/configurator_page.xml",
            "product_configurator_web_3d/static/src/page/configurator_page.js",
        ],
    },
    "installable": True,
    "auto_install": False,
}
