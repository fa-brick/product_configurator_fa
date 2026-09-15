/**
 * manifest_bundles.test.js — Tout fichier JS de `static/src` est-il DÉCLARÉ ?
 *
 * ⚠️ **Le défaut que cette garde empêche a eu lieu, et il était invisible d'ici.** Le
 * 2026-09-14, `page/baked_parts.js` a été ajouté sans être déclaré dans le manifeste. Rien
 * ne l'a signalé : la suite Jest résout ses imports par le disque, pas par un bundle, et
 * elle est restée verte. Ce n'est qu'en ouvrant l'éditeur — un AUTRE module, dans un AUTRE
 * dépôt — qu'on a vu la console dire *« The following modules are needed by other modules
 * but have not been defined »*, en accusant `configurator_page` qui, lui, était déclaré.
 *
 * C'est [[L-001]] du dépôt éditeur : un import non déclaré casse le bundle ENTIER, et
 * l'erreur nomme la victime la plus éloignée. Une suite verte n'en dit rien.
 *
 * ⓘ La garde est volontairement grossière — « présent quelque part dans le manifeste » —
 * parce que c'est l'oubli TOTAL qui casse. La question plus fine de l'ordre et du bon
 * paquet est déjà traitée côté éditeur par `viewer_bundle.test.js`, qui recalcule la
 * fermeture des imports du viewer.
 */
const fs = require("fs");
const path = require("path");

const MODULE = path.join(__dirname, "../..");
const SRC = path.join(MODULE, "static/src");

/** Tous les `.js` de `static/src`, en chemins relatifs au module. */
function jsFiles(dir) {
    const out = [];
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) out.push(...jsFiles(full));
        else if (entry.name.endsWith(".js")) out.push(path.relative(MODULE, full));
    }
    return out;
}

describe("le manifeste déclare tout ce que le module apporte", () => {
    const manifest = fs.readFileSync(path.join(MODULE, "__manifest__.py"), "utf8");

    test("⚠️ aucun `.js` de `static/src` n'est absent des bundles", () => {
        const absents = jsFiles(SRC).filter((f) => !manifest.includes(f));
        expect(absents).toEqual([]);
    });

    test("la garde n'est pas vide — elle voit bien des fichiers", () => {
        expect(jsFiles(SRC).length).toBeGreaterThan(3);
    });
});
