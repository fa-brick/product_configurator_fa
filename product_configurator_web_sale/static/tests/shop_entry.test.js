/** @odoo-module */
/**
 * shop_entry.test.js — Ce que la BOUTIQUE montre d'un produit configurable.
 *
 * ⚠️ **Trois défauts relevés le 2026-09-22 par Gerry, et aucun n'était visible d'un test.**
 * Les deux premiers sont des ABSENCES à obtenir (une question qui ne doit plus être posée,
 * une croix qui ne doit plus être dessinée ici) et le troisième une PROMESSE à tenir (un
 * prix qui s'annonce comme un plancher). Ce fichier lit les gabarits — c'est là que ces
 * trois-là se décident, et ni Jest ni la suite Python ne les regardaient.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const VUE = readFileSync(
    join(__dirname, "..", "..", "views", "templates.xml"), "utf8");
const OVERLAY = readFileSync(
    join(__dirname, "..", "src", "overlay", "configurator_overlay.xml"), "utf8");
const OVERLAY_SCSS = readFileSync(
    join(__dirname, "..", "src", "overlay", "configurator_overlay.scss"), "utf8");

describe("la fiche d'un produit configurable ne pose plus les questions", () => {
    test("⚠️ les sélecteurs de variante s'effacent", () => {
        // Le pari d'origine — « un produit configurable n'a pas de variante, donc pas de
        // sélecteur » — tombe dès qu'une configuration en a créé une. La fiche du JeNo
        // affichait « Type de TopPlate » et « Type de MiddlePlate » : les questions du
        // configurateur, posées une seconde fois et sans bouton pour agir.
        const i = VUE.indexOf("website_sale.variants");
        expect(i).toBeGreaterThan(-1);
        const bloc = VUE.slice(VUE.lastIndexOf("<xpath", i), VUE.indexOf("</xpath>", i));
        expect(bloc).toContain("not product.config_ok");
    });

    test("le bouton du panier s'efface aussi — les deux, ou rien", () => {
        // Un sélecteur sans panier est un choix qui ne mène nulle part ; un panier sans
        // sélecteur vend une configuration que personne n'a faite.
        const i = VUE.indexOf("add_to_cart_wrap");
        const bloc = VUE.slice(VUE.lastIndexOf("<xpath", i), VUE.indexOf("</xpath>", i));
        expect(bloc).toContain("not product.config_ok");
    });

    test("le prix s'annonce comme un PLANCHER, et se tait s'il est nul", () => {
        // « À partir de 0 € » est pire que le silence.
        expect(VUE).toContain(">From<");
        expect(VUE).toContain("product.config_ok and combination_info['price']");
    });
});

describe("la croix a quitté l'overlay pour la page", () => {
    test("l'overlay ne dessine plus la sienne", () => {
        expect(OVERLAY).not.toContain("o_cfg3d_overlay_close");
    });

    test("il donne à la page ce que lui seul sait faire : refermer par l'historique", () => {
        expect(OVERLAY).toContain("onClose=");
        expect(OVERLAY).toContain("this.close()");
    });

    test("et le style de l'ancienne croix est parti avec le bouton", () => {
        // Une règle orpheline se relit comme une intention : la prochaine session la
        // rebrancherait, et l'on aurait deux croix.
        expect(OVERLAY_SCSS).not.toMatch(/^\.o_cfg3d_overlay_close\s*\{/m);
    });
});
