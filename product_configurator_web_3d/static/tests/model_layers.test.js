/**
 * model_layers.test.js — Un modèle du fork se range en ce qu'il DÉCLARE (`models/bo/`) et ce qu'il EXÉCUTE (`models/bll/`) (D-541).
 *
 * ⚠️ Un `def` posé dans un BO, ou un champ posé dans une BLL, défait la règle sans rien casser : Odoo refond les
 *   deux couches en une classe, et seul ce garde-fou le voit.
 * ⚠️ Un module du fork qui a des modèles et manque à `MODULES` n'est pas regardé : la liste se compare au disque.
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = join(__dirname, "..", "..", "..");

/** Les modules du fork qui portent des modèles, tous rangés (W-154). */
const MODULES = [
    "product_configurator_fa",
    "product_configurator_fa_mrp",
    "product_configurator_fa_sale",
    "product_configurator_web_3d",
    "product_configurator_web_3d_environment",
    "product_configurator_web_3d_environment_sale",
    "product_configurator_web_3d_sale",
    "product_configurator_web_3d_sale_drawing",
    "product_configurator_web_sale",
];

function pyFiles(dir) {
    return readdirSync(dir, { recursive: true })
        .filter((f) => f.endsWith(".py") && !f.includes("__pycache__") && !f.endsWith("__init__.py"))
        .map((f) => ({ rel: f, src: readFileSync(join(dir, f), "utf8") }));
}

describe("rangement des modèles du fork en BO et BLL (D-541)", () => {
    test("chaque module du fork qui a des modèles figure dans la liste", () => {
        const withModels = readdirSync(ROOT)
            .filter((d) => d.startsWith("product_configurator") && existsSync(join(ROOT, d, "models")))
            .sort();
        expect(withModels).toEqual([...MODULES].sort());
    });

    for (const mod of MODULES) {
        const models = join(ROOT, mod, "models");

        test(`${mod} : models/ ne porte que bo/, bll/ et son __init__`, () => {
            const top = readdirSync(models).filter((f) => f !== "__pycache__").sort();
            expect(top).toEqual(["__init__.py", "bll", "bo"]);
        });

        test(`${mod} : aucun def dans un fichier BO`, () => {
            const files = pyFiles(join(models, "bo"));
            expect(files.length).toBeGreaterThan(0);
            const found = files.flatMap(({ rel, src }) =>
                [...src.matchAll(/^\s*(?:async\s+)?def\s+(\w+)/gm)].map((m) => `bo/${rel}:${m[1]}`));
            expect(found).toEqual([]);
        });

        test(`${mod} : aucun champ dans un fichier BLL`, () => {
            const files = pyFiles(join(models, "bll"));
            expect(files.length).toBeGreaterThan(0);
            const found = files.flatMap(({ rel, src }) =>
                [...src.matchAll(/^\s+(\w+)\s*=\s*fields\.\w+\(/gm)].map((m) => `bll/${rel}:${m[1]}`));
            expect(found).toEqual([]);
        });

        test(`${mod} : les déclarations se chargent avant la logique`, () => {
            expect(readFileSync(join(models, "__init__.py"), "utf8")).toMatch(/^from \. import bo, bll\b/m);
        });
    }
});
