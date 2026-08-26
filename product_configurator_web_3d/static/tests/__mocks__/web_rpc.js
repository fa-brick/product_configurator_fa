// L'appel réseau, remplacé par une file de réponses que le test pose lui-même.
let queue = [];
module.exports = {
    rpc: async (route, params) => {
        module.exports.calls.push({ route, params });
        return queue.length ? queue.shift() : {};
    },
    calls: [],
    __queue(...responses) { queue = responses; },
    __reset() { queue = []; module.exports.calls = []; },
};
