// `_t` rend la chaîne telle quelle, avec ses substitutions — assez pour éprouver ce qui
// est DIT, sans charger le catalogue.
module.exports = {
    _t: (s, ...args) => {
        let i = 0;
        return String(s).replace(/%\(?(\w+)?\)?s/g, () => String(args[i++] ?? ""));
    },
};
