/** @odoo-module */
/**
 * baked_parts.test.js — SERVIR une piece cuite au lieu de la reconstruire.
 *
 * ⚠️ **Le risque de ce lot n'est pas de ne rien gagner : c'est de servir une forme
 * FAUSSE.** Une piece cuite est une image figee ; si elle se substitue a une piece que la
 * configuration peut changer, ou si son identite se perd en route, le client voit un
 * produit qui n'est pas le sien — et rien ne le dit. Ces tests eprouvent donc surtout ce
 * qui doit RESTER vrai.
 */
import { meshesOf, bakedSolids, bakedPart, facesOfMesh }
    from "@product_configurator_web_3d/page/baked_parts";

/** Une scene glTF reduite a ce qui decide : des mailles, et leur nom. */
const mesh = (name) => ({
    isMesh: true, name, children: [],
    geometry: { userData: {}, boundingBox: null,
                computeBoundingBox() { this.boundingBox = box(); } },
    material: { name: "du fichier" },
});
const box = () => ({
    min: [0, 0, 0], max: [1, 1, 1],
    clone() { return this; },
    applyMatrix4() { return this; },
});
const scene = (children) => ({ children });

describe("les mailles d'un fichier", () => {
    test("une scene plate rend ses mailles", () => {
        expect(meshesOf(scene([mesh("a"), mesh("b")]))).toHaveLength(2);
    });

    test("et une scene IMBRIQUEE aussi — l'export ecrit une hierarchie", () => {
        const parent = { children: [mesh("enfant")] };
        expect(meshesOf(scene([parent]))).toHaveLength(1);
    });

    test("ce qui n'est pas une maille ne compte pas", () => {
        expect(meshesOf(scene([{ children: [] }, mesh("a")]))).toHaveLength(1);
    });

    test("une scene vide ne leve pas", () => {
        expect(meshesOf(null)).toEqual([]);
    });
});

describe("⚠️ L'IDENTITE d'un solide cuit", () => {
    test("elle est celle de la PIECE, jamais le nom de la maille", () => {
        // Le viewer indexe les solides par noeud et les cherche par celui de la piece
        // qu'il monte : y mettre le nom du fichier les rendrait introuvables, et la piece
        // s'afficherait VIDE sans la moindre erreur.
        const [solid] = bakedSolids(scene([mesh("root#f3d_7")]), { nodeId: "c12" });
        expect(solid.nodeId).toBe("c12");
        expect(solid.bakedName).toBe("root#f3d_7");
    });

    test("⚠️ `engineOwned` est POSE — sans lui, le fichier reste invisible", () => {
        // Le viewer ne peut pas reproduire cette forme par son cache `(dessin, op,
        // params)` : elle ne vient d'aucun dessin. Il rebatirait une piece vide.
        const [solid] = bakedSolids(scene([mesh("a")]), { nodeId: "c1" });
        expect(solid.engineOwned).toBe(true);
    });

    test("⚠️ chaque maille recoit SES faces, retrouvees par son NOM", () => {
        // La table est rangee par solide a la cuisson, et l'export nomme la maille
        // `<pieceKey>#<nodeId>` : on la retrouve sans rien DEVINER. A plat, il aurait
        // fallu inferer par le prefixe d'identifiant — ce qui echoue en silence sur un
        // solide ne d'un booleen, lequel agrege les faces de PLUSIEURS fonctions.
        const faces = { f3d_1: [{ id: "f3d_1.face:end@x" }],
                        f3d_2: [{ id: "f3d_2.wall:a" }, { id: "f3d_2.wall:b" }] };
        const solids = bakedSolids(scene([mesh("root#f3d_1"), mesh("root#f3d_2")]),
                                   { nodeId: "c1", faces });
        expect(solids[0].faces).toHaveLength(1);
        expect(solids[1].faces).toHaveLength(2);
    });

    test("⚠️ et elles reviennent sur la GEOMETRIE, la ou le viewer les lit", () => {
        // C'est `geometry.userData.faces` qu'il lit pour en deriver ses plages de
        // triangles. Les poser ailleurs laisserait la piece GRISE, sans la moindre erreur.
        const m = mesh("root#f3d_1");
        bakedSolids(scene([m]), { nodeId: "c1",
                                  faces: { f3d_1: [{ id: "f3d_1.face:end@x" }] } });
        expect(m.geometry.userData.faces).toHaveLength(1);
    });

    test("une maille sans table ne se voit rien poser", () => {
        const m = mesh("root#inconnu");
        bakedSolids(scene([m]), { nodeId: "c1", faces: { f3d_1: [{ id: "x" }] } });
        expect(m.geometry.userData.faces).toBeUndefined();
    });

    test("le nom SANS `#` sert de cle tel quel", () => {
        // Robustesse : un fichier cuit par une version qui nommait autrement ne doit pas
        // faire perdre ses faces en silence.
        expect(facesOfMesh({ name: "f3d_9" }, { f3d_9: [{ id: "a" }] })).toHaveLength(1);
    });
});

describe("⚠️ LA SUBSTITUTION NE SE FAIT QUE SI ELLE EST SURE", () => {
    const THREE = {
        Matrix4: class { clone() { return this; } },
        Box3: class {
            constructor() { this.min = { toArray: () => [0, 0, 0] };
                            this.max = { toArray: () => [1, 1, 1] }; }
            union() { return this; }
        },
    };

    test("sans cuisson pour ce noeud, elle rend NULL — et le moteur construit", () => {
        // C'est ce qui rend le lot sans risque : le chemin d'avant reste le defaut, et
        // toute incertitude y retombe.
        expect(bakedPart(THREE, { id: "c1" }, null, new Map())).toBe(null);
    });

    test("un fichier SANS maille rend null lui aussi", () => {
        // Un fichier vide servirait une piece vide, ce qui est pire que de la rebatir.
        const loaded = new Map([["c1", { scene: scene([]), faces: {} }]]);
        expect(bakedPart(THREE, { id: "c1" }, null, loaded)).toBe(null);
    });

    test("et avec une maille, la piece prend la forme que `build()` attend", () => {
        const loaded = new Map([["c1", {
            scene: scene([mesh("root#f3d_1")]),
            faces: { f3d_1: [{ id: "x" }] },
        }]]);
        const part = bakedPart(THREE, { id: "c1" }, null, loaded);
        expect(part.solids).toHaveLength(1);
        expect(part.sketches).toEqual([]);
        expect(part.faces).toHaveLength(1);
        expect(part.bboxWorld).toEqual({ min: [0, 0, 0], max: [1, 1, 1] });
    });
});
