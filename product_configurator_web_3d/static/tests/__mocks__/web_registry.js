const store = new Map();
module.exports = {
    registry: {
        category(name) {
            if (!store.has(name)) store.set(name, new Map());
            const cat = store.get(name);
            return {
                add(key, value) { cat.set(key, value); return this; },
                get(key, fallback) { return cat.has(key) ? cat.get(key) : fallback; },
                contains(key) { return cat.has(key); },
                getAll() { return [...cat.values()]; },
            };
        },
    },
};
