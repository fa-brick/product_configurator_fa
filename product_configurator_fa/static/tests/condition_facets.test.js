/**
 * condition_facets.test.js — le découpage d'un résumé en pastilles (B2, D-203).
 *
 * ⚠️ Le cas qui compte est le résumé VIDE : `"".split(sep)` rend `[""]`, donc une
 * pastille sans texte là où il n'y a AUCUNE condition — et c'est le cas le plus
 * fréquent, la plupart des lignes n'en portant pas.
 */
import {FACET_SEPARATOR, splitFacets} from "../src/js/condition_facets.esm.js";

describe("Un résumé de condition se découpe en pastilles", () => {
    test("⚠️ un résumé vide ne donne AUCUNE pastille, et surtout pas une vide", () => {
        expect(splitFacets("")).toEqual([]);
        expect(splitFacets(undefined)).toEqual([]);
        expect(splitFacets(false)).toEqual([]);
    });

    test("une règle donne une pastille", () => {
        expect(splitFacets("Colour = Red / Blue")).toEqual(["Colour = Red / Blue"]);
    });

    test("deux règles donnent deux pastilles, le lien restant DANS la seconde", () => {
        // Le lien appartient à la pastille qu'il précède : c'est ainsi que le
        // serveur l'écrit, et le découpage ne doit pas le mettre à part.
        const resume = `Colour = Red${FACET_SEPARATOR}or Size = Large`;
        expect(splitFacets(resume)).toEqual(["Colour = Red", "or Size = Large"]);
    });

    test("⚠️ une valeur qui CONTIENT le séparateur ne casse pas le découpage", () => {
        // Le séparateur est un caractère que les noms de valeur ne portent pas ;
        // si cela changeait, ce test dirait où.
        expect(splitFacets("Colour = Red")).toHaveLength(1);
    });
});
