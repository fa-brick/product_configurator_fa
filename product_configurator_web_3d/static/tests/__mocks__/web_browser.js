// `browser` d'Odoo — les minuteries seules, celles de la page.
module.exports = {
    browser: {
        setTimeout: (...a) => setTimeout(...a),
        clearTimeout: (...a) => clearTimeout(...a),
    },
};
