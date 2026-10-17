from . import product_attribute
from . import product_config
from . import product_config_hand
from . import product_config_web
from . import product_template
# ⓘ Le point d'entrée du DIALOGUE — `web3d_open_configuration`, appelé par le devis ET par
# l'ordre de fabrication.
# ⚠️ Le remettre dans le module du devis forcerait la fabrication à dépendre de la vente.
from . import product_template_web3d
# ⓘ La RECONFIGURATION d'une variante ouvre elle aussi la page 3D, pas l'assistant OCA.
from . import product_product_web3d
from . import ir_websocket
# La condition d'un EMPLACEMENT, écrite dans le dialogue du configurateur (D-267).
from . import placement_condition
# Les traductions JS de la page, servies au SITE (D-353).
from . import ir_http
# L'IMAGE d'une variante née d'une configuration (D-399, lot 5).
from . import product_config_variant_image
# Les MONTANTS affichés par la page : supplément de chaque réponse, total avec sa devise (W-100).
from . import product_config_price_label
