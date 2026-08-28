"""Un attribut dont les valeurs pointent un produit DÉCLARE qu'il en pointe.

⚠️ **Le champ `product_id` existait bien avant le type de valeur** — et rien ne
l'accompagnait. Les données qui s'en servent sont donc restées sur le type par
défaut (« valeur »), que la garde de D-196 refuse désormais : le premier
enregistrement d'un tel attribut échouerait, sur une contradiction que personne
n'a écrite.

⚠️ **Trouvé parce que la DÉMO DU MODULE a refusé de s'installer**, pas par
raisonnement : cinq attributs de la démo posaient `product_id` sans rien en
déclarer. Mesuré ensuite sur `fabk18` et `fabk18_test` : aucun attribut réel
dans ce cas — mais aucune raison de croire que c'est vrai partout.

ⓘ La réciproque n'est pas faite : un attribut de type « produit » dont aucune
valeur ne pointe rien reste parfaitement licite (il attend d'être rempli).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE product_attribute a
           SET value_type = 'product'
         WHERE COALESCE(a.value_type, 'value') = 'value'
           AND EXISTS (SELECT 1 FROM product_attribute_value v
                        WHERE v.attribute_id = a.id
                          AND v.product_id IS NOT NULL)
        """
    )
    if cr.rowcount:
        _logger.info(
            "%s attribut(s) pointaient un produit sans le déclarer : type corrigé.",
            cr.rowcount,
        )
