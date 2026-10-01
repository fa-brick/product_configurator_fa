// Mock OWL minimal — seules les fonctions que les modules éprouvés importent.
// ⚠️ Volontairement PAUVRE : ce harnais éprouve la LOGIQUE de la page, pas le rendu
// d'OWL, qui est déjà éprouvé chez Odoo. Un mock riche donnerait l'illusion de tester
// le montage.
module.exports = {
    Component: class Component {},
    useState: (s) => s,
    useRef: () => ({ el: null }),
    onWillStart: (fn) => fn && fn(),
    onMounted: () => {},
    onWillUnmount: () => {},
    // ⓘ Branché TOUT DE SUITE sur la cible : le banc tient lieu de montage, et c'est
    // l'abonnement qu'il éprouve, pas le cycle de vie d'OWL.
    useExternalListener: (target, name, handler) => target.addEventListener?.(name, handler),
    xml: (strings) => String(strings),
};
