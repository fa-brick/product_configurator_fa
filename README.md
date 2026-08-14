# product_configurator_fa

Configurateur de produits pour Odoo 18 — socle du configurateur fa-brick.

## Provenance

Ce dépôt est un **fork** de [OCA/product-configurator](https://github.com/OCA/product-configurator),
branche `18.0`, sous licence **AGPL-3**. L'attribution d'origine (Pledra, Odoo Community
Association) est conservée dans chaque manifeste, comme l'exige la licence.

⚠️ **L'amont ne sera pas suivi.** La divergence prévue est trop importante pour que des
synchronisations aient un sens (décision D-096). Ce qui était « des modifications à reporter »
devient donc **notre propre code** — et les migrations d'une version d'Odoo à l'autre, que l'OCA
portait, deviennent les nôtres.

## Renommage — pourquoi les modules s'appellent `*_fa`

Odoo résout un module par le **premier chemin d'addons** et ignore silencieusement l'autre. Tant
que le nom d'origine subsiste, deux installations peuvent diverger sans le moindre message
d'erreur. Le renommage n'est donc pas cosmétique : il rend l'ambiguïté impossible.

| module | rôle |
|---|---|
| `product_configurator_fa` | le cœur — règles, session, attributs |
| `product_configurator_fa_sale` | session → devis |
| `product_configurator_fa_mrp` | configuration → nomenclature |

## Vérification statique

Un renommage de module ne casse pas au chargement : il casse **plus tard**, à l'exécution, quand
`env.ref()` ne trouve rien ou qu'OWL réclame un template absent. Trois modes de panne, tous
silencieux, tous couverts par :

```bash
python3 tools/check_module_refs.py .
```

Il signale les identifiants XML irrésolus, les survivances de l'ancien nom, et les templates QWeb
réclamés par du JavaScript sans définition correspondante. C'est ce dernier contrôle qui a trouvé
`boolean_button_widget.esm.js` lors du renommage initial — la définition avait été renommée, pas la
référence.

⚠️ Ce contrôle **ne remplace pas les tests** : il vérifie que les références se résolvent, pas que
le code fait ce qu'il doit.

## Tests

**85 tests** hérités de l'OCA — 81 dans le cœur, 4 dans `_sale` et `_mrp`. Ils constituent le filet
de tout ce qui suit : aucun lot ne commence avant qu'ils soient verts sous le nouveau nom.

```bash
odoo -d <base> -i product_configurator_fa,product_configurator_fa_sale,product_configurator_fa_mrp \
     --test-enable --stop-after-init
```
