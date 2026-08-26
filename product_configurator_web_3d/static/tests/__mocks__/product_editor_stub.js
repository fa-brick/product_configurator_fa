// ⚠️ L'ÉDITEUR N'EST PAS DANS CE DÉPÔT. Le fork en dépend comme MODULE Odoo, pas comme
// source : ses fichiers vivent dans `product_3Dmodel`, et pointer dessus lierait ces
// tests à la présence d'une copie voisine. Ce qui s'éprouve ici est la logique de la
// PAGE ; le viewer, lui, est éprouvé là-bas, avec ses 3 200 tests.
module.exports = new Proxy({}, {
    get: () => class Stub {},
});
