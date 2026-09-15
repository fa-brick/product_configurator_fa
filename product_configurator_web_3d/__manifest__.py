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
        # ⚠️ **UNE SEULE LIGNE, ET C'EST UNE DÉCISION DE SÉCURITÉ.** Le viewer va
        # chercher les textures par URL — `/web/image/product.model3d.texture/<id>/image`,
        # construite dans `pbr_material.js` —, et ce contrôleur vérifie le droit de
        # LECTURE sur l'enregistrement. Sans cette ligne, un visiteur reçoit un 403 par
        # texture et la 3D reste sans matière, comme elle l'était jusqu'au 2026-09-06.
        #
        # ⓘ Ce qui est ouvert : la LECTURE des images de texture, par identifiant. Ce
        # sont des images de catalogue — un carbone, un bois — que tout visiteur voit de
        # toute façon sur le produit rendu. Rien d'autre du modèle 3D n'est ouvert : ni
        # les pièces, ni les zones, ni les matières, que le serveur compose et sert
        # lui-même en `sudo`.
        #
        # ⚠️ Elle vit ICI et non dans `product_editor` : la permission arrive avec la
        # fonctionnalité qui l'exige. L'éditeur seul n'a aucune raison d'ouvrir quoi que
        # ce soit au public.
        "security/ir.model.access.csv",
        "views/product_view.xml",
        "views/product_attribute_view.xml",
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
            # ⚠️ **AVANT la page qui l'appelle** — l'ordre d'un bundle est significatif
            # ([[L-001]] côté éditeur) : ce module n'était déclaré NULLE PART, et son
            # absence cassait le bundle ENTIER en accusant `configurator_page`.
            "product_configurator_web_3d/static/src/page/baked_parts.js",
            "product_configurator_web_3d/static/src/page/configurator_page.js",
        ],
        # ══ CE QUE LA FORME « CARTE » DOIT AU BACK-OFFICE ══════════════════════
        #
        # ⚠️ Une seule ligne, et c'est une garde : le dialogue de vente d'Odoo
        # VALIDE `display_type` contre une liste fermée et choisit son gabarit
        # sans cas par défaut. Sans ce correctif, une carte posée sur un produit
        # ORDINAIRE fait tomber son écran (D-258).
        #
        # ⓘ Aucun module-pont : `sale` est déjà en amont d'ici
        # (`product_configurator_web_3d` → `product_editor` → `sale`).
        # ══ LE MÊME CONFIGURATEUR, EN DIALOGUE AU BACK-OFFICE — D-262 ══════════
        #
        # ⓘ La PAGE est déclarée ici, et non dans le pont de vente : elle
        # appartient à ce module, et le dialogue d'une ligne de devis n'est qu'un
        # de ses hôtes. L'ordre reste significatif ([[L-001]]) : l'état, la page,
        # puis l'action qui la monte.
        #
        # ⓘ Rien du viewer : `product_editor` met déjà ses 65 fichiers dans ce
        # paquet — c'est le FRONT qui avait dû les recevoir, pas l'inverse.
        "web.assets_backend": [
            "product_configurator_web_3d/static/src/sale_card_tolerance.js",
            "product_configurator_web_3d/static/src/configurator_state.js",
            "product_configurator_web_3d/static/src/page/configurator_page.scss",
            "product_configurator_web_3d/static/src/page/configurator_page.xml",
            # ⚠️ **AVANT la page qui l'appelle** — l'ordre d'un bundle est significatif
            # ([[L-001]] côté éditeur) : ce module n'était déclaré NULLE PART, et son
            # absence cassait le bundle ENTIER en accusant `configurator_page`.
            "product_configurator_web_3d/static/src/page/baked_parts.js",
            "product_configurator_web_3d/static/src/page/configurator_page.js",
            "product_configurator_web_3d/static/src/page/configurator_action.scss",
            "product_configurator_web_3d/static/src/page/configurator_action.xml",
            "product_configurator_web_3d/static/src/page/configurator_action.js",
        ],
    },
    "installable": True,
    "auto_install": False,
}
