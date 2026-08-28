/**
 * Doublure du champ Many2one d'Odoo — le harnais Jest tourne hors Odoo.
 *
 * ⓘ Elle ne simule rien : elle existe pour que l'import se résolve. Ce qui est
 * éprouvé ici est le DÉCOUPAGE d'un résumé en pastilles, une fonction pure.
 */
export class Many2OneField {
    static props = {};
}
export const many2OneField = {
    component: Many2OneField,
    extractProps: () => ({}),
};
