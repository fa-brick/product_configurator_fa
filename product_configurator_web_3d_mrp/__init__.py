# ⓘ **AUCUN import ici, et surtout pas `tests`.** Ce pont n'a pas de modèle Python :
# Odoo donne déjà `product_tmpl_id` sur un ordre de fabrication, et
# `product_configurator_fa_mrp` donne `config_ok` et `config_session_id` — il ne restait
# qu'à brancher le geste, côté client.
#
# ⚠️ Odoo DÉCOUVRE le paquet `tests` tout seul. L'importer d'ici charge le cadre de test
# en production, et le serveur le dit : *« Importing test framework, avoid importing from
# business modules and when not running in test mode »*.
