/**
 * LES COMMENTAIRES XML DU FORK NE CONTIENNENT PAS `--` — [[L-242]], récidive du 2026-10-01.
 *
 * La norme XML interdit deux tirets accolés dans un commentaire. Odoo refuse alors le fichier
 * de gabarits ENTIER : la page du configurateur ne se montait plus (« Missing template:
 * product_configurator_web_3d.ConfiguratorPage »), pendant que la suite Jest restait verte.
 * La faute était un nom de modificateur CSS cité dans un commentaire (`o_cfg3d_side` suivi de
 * son modificateur à deux tirets) — le geste est naturel, d'où ce garde.
 *
 * ⓘ `product_editor` a son garde complet (`xml_well_formed.test.js`, par `DOMParser`) ; ce
 * banc-ci tourne sans jsdom, et vise la faute qui a déjà frappé deux fois.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "../../..");
const SKIPPED = new Set(["node_modules", "__pycache__", ".git"]);

function xmlFiles(dir, out = []) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (SKIPPED.has(entry.name)) continue;
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) xmlFiles(full, out);
        else if (entry.name.endsWith(".xml")) out.push(full);
    }
    return out;
}

/** Les commentaires fautifs d'un document : `ligne: extrait`. */
function badComments(source) {
    const faults = [];
    for (const match of source.matchAll(/<!--([\s\S]*?)-->/g)) {
        const body = match[1];
        const at = body.indexOf("--");
        // ⓘ Un commentaire qui finit par un tiret (`-->` précédé de `-`) est fautif aussi.
        if (at === -1 && !body.endsWith("-")) continue;
        const line = source.slice(0, match.index).split("\n").length;
        const excerpt = at === -1 ? body.slice(-20) : body.slice(Math.max(0, at - 20), at + 20);
        faults.push(`${line}: …${excerpt.replace(/\s+/g, " ")}…`);
    }
    return faults;
}

const files = xmlFiles(ROOT);

describe("aucun `--` dans un commentaire XML du fork", () => {
    test("le parcours trouve bien des fichiers (un parcours vide passerait au vert, L-118)", () => {
        expect(files.length).toBeGreaterThan(10);
        expect(files.some((file) => file.endsWith("configurator_page.xml"))).toBe(true);
    });

    test.each(files.map((file) => [path.relative(ROOT, file), file]))("%s", (relative, file) => {
        expect(badComments(fs.readFileSync(file, "utf8"))).toEqual([]);
    });

    test("⚠️ le garde voit ROUGE sur la faute réelle", () => {
        expect(badComments("<a>\n<!-- ⓘ `--panel` : la colonne -->\n</a>")).toHaveLength(1);
        expect(badComments("<a><!-- fin par un tiret --->\n</a>")).toHaveLength(1);
        expect(badComments("<a><!-- un tiret - seul, c'est permis --></a>")).toEqual([]);
    });
});
