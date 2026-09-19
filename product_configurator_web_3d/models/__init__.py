from . import product_attribute
from . import product_config
from . import product_config_hand
from . import product_config_web
from . import product_template
# ⓘ Le point d'entrée du DIALOGUE — `web3d_open_configuration`. Il vivait dans le
# module du devis, alors qu'il n'a rien de commercial : le devis et l'ordre de
# fabrication l'appellent tous les deux, et deux copies auraient divergé.
from . import product_template_web3d
# ⓘ La RECONFIGURATION d'une variante, redirigée elle aussi vers la page 3D : ses
# deux boutons ouvraient l'assistant OCA, mort depuis le 2026-09-19.
from . import product_product_web3d
from . import ir_websocket
# La condition d'un EMPLACEMENT, écrite dans le dialogue du configurateur (D-267).
from . import placement_condition
