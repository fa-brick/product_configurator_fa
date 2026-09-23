/** @odoo-module */
/**
 * viewer_props.test.js — Ce que la page DOIT donner au viewer.
 *
 * ⚠️ **Une prop absente ne lève pas.** Le viewer se rabat sur ce qu'il sait faire
 * seul — refaire une extrusion depuis son dessin — et rend une pièce PLAUSIBLE et
 * fausse : sans ses trous, sans ses chanfreins, sans ses matières. Relevé de Gerry
 * le 2026-09-07, sur la plaque du JeNo ; aucun test ne pouvait le voir, et la
 * console restait muette ([[L-188]]).
 *
 * ⓘ On éprouve donc le GABARIT : ces quatre props sont le contrat entre la page et
 * le viewer, et leur oubli est silencieux par construction.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const TEMPLATE = readFileSync(
    join(__dirname, "..", "src", "page", "configurator_page.xml"), "utf8");

/** Le bloc de la balise `<PartViewer3D …>`, attributs compris. */
function viewerTag() {
    const start = TEMPLATE.indexOf("<PartViewer3D");
    expect(start).toBeGreaterThan(-1);
    return TEMPLATE.slice(start, TEMPLATE.indexOf("/>", start));
}

/**
 * ⚠️ **La CAMÉRA se demande avant le premier rendu.** Posée après la construction,
 * elle arrivait 2,5 s trop tard : le viewer avait déjà cadré la scène tout seul, et
 * l'on voyait la pièce à deux endroits (sonde du 2026-09-07 — cadrage automatique à
 * 2 405 ms, vue par défaut à 4 899 ms ; après correction : 2 437 et 2 440 ms).
 *
 * ⓘ On éprouve le CHEMIN, pas le chronomètre : la demande doit partir de
 * `onWillStart`, là où l'état arrive, et non du seul `_applyModel` — le premier
 * chargement ne passe pas par lui, et c'est justement celui qui compte.
 */
describe("la vue par défaut de la page", () => {
    const SOURCE = readFileSync(
        join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");

    /** Le corps d'une méthode ou d'un bloc, depuis son entête. */
    function bodyAfter(marker) {
        const start = SOURCE.indexOf(marker);
        expect(start).toBeGreaterThan(-1);
        return SOURCE.slice(start, start + 1400);
    }

    test("elle est demandée dès l'arrivée de l'état, dans `onWillStart`", () => {
        expect(bodyAfter("onWillStart(async () => {")).toContain("_settleCamera()");
    });

    test("elle est demandée aussi quand l'état est REMPLACÉ", () => {
        expect(bodyAfter("async _applyModel(payload)")).toContain("_settleCamera()");
    });

    test("elle ne se demande QU'UNE FOIS — sinon un clic ramènerait la caméra", () => {
        expect(bodyAfter("_settleCamera() {")).toContain("_cameraSettled");
    });

    test("la photo s'efface quand la SCÈNE est là, pas quand la caméra se pose", () => {
        // Les deux étaient liés : lever `ready` dans `_settleCamera` faisait dépendre
        // l'attente d'une pose, et la pose d'une construction.
        expect(bodyAfter("_settleCamera() {")).not.toContain("state.ready = true");
    });

    test("quitter l'isolation RAMÈNE la vue caméra en cours — celle du produit, avec sa cible", () => {
        // Gerry (2026-09-23) : le double clic vise la pièce ; en quittant, la vue en cours
        // rend sa cible. La vue vient du serveur AVEC `target` ; sans vue, la matière.
        const select = bodyAfter("_select(nodeId, isolated, { broadcast = true } = {}) {");
        expect(select).toContain("if (isolated && nodeId) this._frameOn(nodeId);");
        expect(select).toContain("else if (before.isolated) this._returnToView();");
        const back = bodyAfter("_returnToView() {");
        expect(back).toContain("this.state.model?.camera");
        expect(back).toContain("target: { root: true }");
    });
});

describe("la page publique et son viewer", () => {
    const tag = viewerTag();

    test("elle passe les POSES calculées par le moteur", () => {
        expect(tag).toContain("getResolvedWorldByNodeId");
    });

    test("elle passe les VOLUMES du moteur — percés, chanfreinés", () => {
        // Sans eux : plus de perçage, plus de chanfrein, et rien ne le dit.
        expect(tag).toContain("getResolvedSolidsByNodeId");
    });

    test("elle passe les CORPS CUITS — sinon un quart de tour sur chaque pièce servie", () => {
        // ⚠️ Cette prop MANQUAIT (relevé du 2026-09-22), et personne ne l'avait vu parce
        // que la cuisson n'atteignait pas la page (`toViewModel` la laissait tomber).
        // Sans elle, un corps cuit repasse par le groupe de son esquisse et reçoit la
        // matrice du plan une seconde fois (mesuré sur le bras, dans l'éditeur).
        expect(viewerTag()).toContain("getResolvedBakedSolids.bind");
    });

    test("⚠️ elle passe les PASSES FINALES — sept gravures manquaient, sans une erreur", () => {
        // Relevé du 2026-09-22 sur le JeNo : sept `engrave` visibles et complètes dans la
        // définition, aucune à l'écran — le gabarit ne passait aucune de ces trois props.
        // Cette garde avait été écrite « pour cette famille exacte » et ne les vérifiait
        // pas. Le moteur les publie avec l'arbre (D-330) ; la page les passe.
        const tag = viewerTag();
        expect(tag).toContain('engravingsByPiece="state.postBuild.byPiece"');
        expect(tag).toContain('engravingsByNode="state.postBuild.byNode"');
        expect(tag).toContain('perforationsByPiece="state.postBuild.perforations"');
    });

    test("⚠️ elle passe la SÉLECTION au viewer, et en reçoit clic, double clic et survol (D-333)", () => {
        const tag = viewerTag();
        expect(tag).toContain('pieces="viewerPieces"');                 // isolé, ou tout
        expect(tag).toContain('selectedNodeIds="selectedNodeIds"');
        expect(tag).toContain('selectableNodeIds="selectableNodeIds"');
        expect(tag).toContain('onSelectPiece.bind="onSelectPiece"');
        expect(tag).toContain('onActivatePiece.bind="onActivatePiece"');
    });

    test("⚠️ le survol ne NOMME rien — le contour orange du viewer suffit, comme dans l'éditeur", () => {
        // Arbitrage Gerry (2026-09-23) : pas de cartouche avec le nom de la pièce. Le viewer
        // contoure en orange ce qu'un clic pourrait désigner, et rien d'autre.
        expect(viewerTag()).not.toContain("onHoverPiece");
        expect(TEMPLATE.replace(/<!--[\s\S]*?-->/g, "")).not.toContain("o_cfg3d_hover");
    });

    test("⚠️ une pièce sélectionnée : la FLÈCHE de retour puis son nom en en-tête — ni fil d'Ariane, ni bouton en bas", () => {
        // Maquette de Gerry (2026-09-23) : l'en-tête montre la navigation, les questions
        // de la pièce viennent dessous.
        const body = TEMPLATE.replace(/<!--[\s\S]*?-->/g, "");
        const head = body.slice(body.indexOf('o_cfg3d_title--piece'), body.indexOf('t-else="" class="o_cfg3d_title"'));
        expect(head).toContain('class="o_cfg3d_backarrow"');
        // Flèche et croix : les icônes Odoo (`oi`) des bundles, pas un SVG à nous.
        expect(head).toContain('class="oi oi-arrow-left"');
        expect(head).not.toContain("<svg");
        expect(body.slice(body.indexOf('class="o_cfg3d_close"'), body.indexOf("</button>", body.indexOf('class="o_cfg3d_close"'))))
            .toContain('class="oi oi-close"');
        expect(head).toContain('this.onClearSelection()');
        expect(head).toContain('t-esc="selectedPlacement.label"');
        expect(body).not.toContain("o_cfg3d_crumbs");
        expect(body).not.toContain("o_cfg3d_back\"");
        expect(body).not.toContain("o_cfg3d_piece_title");
        // Isolée par double clic : pas de bouton « voir tout », la flèche ramène à la racine.
        expect(body).not.toContain("o_cfg3d_showall");
        expect(body).not.toContain("onExitIsolation");
    });

    test("les questions du produit et celles d'une pièce passent par le MÊME gabarit", () => {
        expect(TEMPLATE.match(/t-call="product_configurator_web_3d.Question"/g)).toHaveLength(2);
        expect(TEMPLATE).toContain('t-name="product_configurator_web_3d.Question"');
        // Plus aucun `onPick` direct dans le gabarit : une seule porte, `onAnswer`.
        expect(TEMPLATE.replace(/<!--[\s\S]*?-->/g, "")).not.toContain("this.onPick(");
    });

    test("elle passe l'identité de la PIÈCE racine — sinon aucune matière", () => {
        // Les zones sont rangées par pièce (D-166) : sans cet identifiant, elles
        // ne trouvent personne et la racine reste grise.
        expect(tag).toContain("rootPieceId");
    });

    test("elle passe le NŒUD racine — par lui, son volume construit", () => {
        expect(tag).toContain("rootNodeId");
    });

    test("elle NE DESSINE PAS les traits d'esquisse", () => {
        // Le dessin sert à éditer. Sur un écran où l'on ne peut rien modifier, ses
        // traits font passer une gravure pour un contour posé sur la pièce.
        expect(tag).toContain('showSketchLines="false"');
    });

    test("⚠️ elle REFERME la boucle de sélection — l'aller ET le retour", () => {
        // `onSelectPiece` est l'aller (souris ET doigt) ; `selectedNodeIds` est le retour,
        // et la seule chose qui allume le contour de SÉLECTION. Sans le retour, seul le
        // SURVOL peignait — donc jamais au doigt, qui ne survole pas (relevé de Gerry,
        // 2026-09-22 : « actif sur desktop, pas sur mobile »). Depuis D-333 le retour passe
        // par la prop de PIÈCES, plus par celle des esquisses.
        expect(tag).toContain('onSelectPiece.bind="onSelectPiece"');
        expect(tag).toContain('selectedNodeIds="selectedNodeIds"');
        expect(tag).not.toContain("selectedSketchId=");
    });

    test("⚠️ l'identité désignée voyage TELLE QUELLE, sans normalisation", () => {
        // Le viewer rend le `nodeId` de la POSE cliquée. L'analyser ici allumerait TOUTES
        // les poses d'un modèle au lieu de celle qu'on a touchée — défaut mesuré dans
        // l'éditeur le 2026-09-13. Une seule définition de `onSelectPiece`, aussi : deux
        // méthodes du même nom, et c'est la dernière qui gagne en silence (2026-09-23).
        const SRC = readFileSync(
            join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");
        expect(SRC.match(/^    onSelectPiece\(/gm)).toHaveLength(1);
        const bloc = SRC.slice(SRC.indexOf("    onSelectPiece(nodeId) {"),
                               SRC.indexOf("    onSelectPiece(nodeId) {") + 220);
        expect(bloc).toContain("this._select(nodeId && this.selectableNodeIds.has(nodeId) ? nodeId : null");
    });

    test("elle passe les zones de matière", () => {
        expect(tag).toContain("zonesByPiece");
    });

    test("⚠️ et PLUS `zoneMaterialsByNode` — la prop a été retirée, pas oubliée", () => {
        // Elle alimentait les EXCEPTIONS de matière par placement, parties avec les canaux
        // de réponses le 2026-09-08 (D-268, commit 5fd3b4d) : sans canal, il n'y a plus
        // rien à apparier. Le viewer ne la déclare plus non plus.
        //
        // ⚠️ **Ce test l'a réclamée pendant SEPT JOURS**, rouge et muet — le commit qui
        // retirait la prop n'a pas touché à son test, et la suite Jest de ce dépôt n'est
        // pas dans le réflexe. C'est la seconde fois en une semaine dans ce projet, après
        // deux tests de caméra restés rouges quatre jours pour la même raison.
        //
        // ⓘ Il reste ici en NÉGATIF plutôt que d'être effacé : si la prop revient un jour,
        // c'est une décision, et elle doit se voir.
        expect(tag).not.toContain("zoneMaterialsByNode");
    });
});


describe("la carte d'une réponse, quand elle n'a pas de vignette", () => {
    const TEMPLATE_PAGE = readFileSync(
        join(__dirname, "..", "src", "page", "configurator_page.xml"), "utf8");

    test("le CADRE ne se dessine que s'il y a une image", () => {
        // ⚠️ Un cadre vide se lit comme un chargement en panne. Une valeur qui ne
        // désigne rien n'a pas d'image : la carte se réduit à son libellé
        // (relevé de Gerry, 2026-09-07).
        expect(TEMPLATE_PAGE).toContain('<span t-if="value.image" class="o_cfg3d_card_shot">');
    });

    test("le libellé, lui, reste toujours là", () => {
        expect(TEMPLATE_PAGE).toContain('class="o_cfg3d_card_label"');
    });
});

describe("le dialogue n'ajoute pas sa marge autour de la scène", () => {
    const SCSS_ACTION = readFileSync(
        join(__dirname, "..", "src", "page", "configurator_action.scss"), "utf8");

    test("le corps du dialogue perd le `padding` d'Odoo", () => {
        expect(SCSS_ACTION.replace(/\s+/g, " ")).toContain("o_cfg3d_action) { padding: 0;");
    });
});

describe("l'AMBIANCE du produit atteint le viewer", () => {
    const SOURCE = readFileSync(
        join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");
    const PAYLOAD = readFileSync(
        join(__dirname, "..", "..", "models", "product_config_web.py"), "utf8");

    test("le gabarit la passe — sans quoi la page rend les constantes du moteur", () => {
        // ⓘ Son absence ne LÈVE pas : le viewer se rabat sur son studio en dur, et la page
        // affiche une pièce plausible sous un éclairage que personne n'a choisi. C'est
        // exactement le mode de panne de ce fichier ([[L-188]]).
        expect(viewerTag()).toContain("ambience=");
    });

    test("elle vient de l'ÉTAT, pas d'une lecture du navigateur", () => {
        // Un visiteur n'a de droit sur aucun de ces modèles : un `read` côté page
        // reviendrait vide, et l'ambiance serait silencieusement ignorée.
        expect(SOURCE).toContain("this.state.model?.ambience");
    });

    test("⚠️ `undefined` et jamais `null` — OWL refuse une prop NULLE", () => {
        // Dans OWL, `optional` autorise une prop ABSENTE et jamais une prop nulle. Un
        // `null` ne se verrait qu'au jour où quelqu'un ouvre le mode debug, et l'écran
        // mourrait alors en emportant son propre diagnostic ([[L-178]]).
        const bloc = SOURCE.slice(SOURCE.indexOf("get ambience()"),
                                  SOURCE.indexOf("get rootPieceId()"));
        expect(bloc).toContain("|| undefined");
    });

    test("le serveur la monte en SUDO — et par `js_row`, jamais recopiée", () => {
        // Une seconde table de correspondance finirait par diverger de celle de l'éditeur,
        // et le symptôme serait un réglage qui marche là-bas et pas ici ([[L-073]]).
        expect(PAYLOAD).toContain('"ambience": self._web_ambience(model3d)');
        const bloc = PAYLOAD.slice(PAYLOAD.indexOf("def _web_ambience"),
                                   PAYLOAD.indexOf("def _web_scene_models"));
        expect(bloc).toContain("sudo()");
        expect(bloc).toContain("js_row()");
    });

    test("⚠️ les réglages COÛTEUX passent tels quels — c'est un arbitrage", () => {
        // « Les rendre disponibles sur mobile si c'est ce que veut celui qui a édité la
        // scène » (Gerry, 2026-09-18). Ce test existe pour qu'une session ultérieure ne
        // rajoute pas un filtre ici en croyant bien faire : l'éditeur AVERTIT à la place.
        const bloc = PAYLOAD.slice(PAYLOAD.indexOf("def _web_ambience"),
                                   PAYLOAD.indexOf("def _web_scene_models"));
        for (const clef of ["groundReflection", "ground_reflection",
                            "hdriUrl", "hdri_background", "pop("]) {
            expect(bloc).not.toContain(clef);
        }
    });

    test("la photo d'environnement est LISIBLE par un visiteur", () => {
        // ⚠️ Son URL est `/web/content/product.model3d.render.preset/<id>/hdri`, servie
        // telle quelle sur la page publique. Sans droit de lecture, le navigateur reçoit
        // un 403 et la pièce se rend sans sa photo — EN SILENCE. C'est le même mur que
        // celui des textures, franchi de la même façon.
        const ACL = readFileSync(
            join(__dirname, "..", "..", "security", "ir.model.access.csv"), "utf8");
        const ligne = ACL.split("\n").find(
            (l) => l.includes("model_product_model3d_render_preset"));
        expect(ligne).toBeDefined();
        expect(ligne).toContain("base.group_public");
        // Lecture SEULE : un visiteur ne règle pas l'ambiance d'un produit.
        expect(ligne.trim().endsWith("1,0,0,0")).toBe(true);
    });
});


describe("LA SORTIE de la page — la croix, et pour ses DEUX hôtes", () => {
    const XML = readFileSync(
        join(__dirname, "..", "src", "page", "configurator_page.xml"), "utf8");
    const SOURCE = readFileSync(
        join(__dirname, "..", "src", "page", "configurator_page.js"), "utf8");

    test("c'est la PAGE qui dessine la croix, pas son hôte", () => {
        // ⚠️ Tant qu'elle vivait dans l'overlay de la boutique, elle manquait partout où
        // l'on arrive par NAVIGATION — la grille, un courriel, un clic donné avant la fin
        // de la préparation. Mesuré le 2026-09-22 : zéro croix dans `/configurator/<jeton>`.
        expect(XML).toContain('class="o_cfg3d_close"');
        expect(XML).toContain('t-if="canClose"');
    });

    test("la sortie vient de l'HÔTE ou de l'ÉTAT — les deux, jamais l'un seul", () => {
        const bloc = SOURCE.slice(SOURCE.indexOf("get canClose()"),
                                  SOURCE.indexOf("onCloseClick()"));
        expect(bloc).toContain("this.props.onClose");
        expect(bloc).toContain("productUrl");
    });

    test("⚠️ l'hôte qui a DÉJÀ un cadre n'en reçoit pas une SECONDE", () => {
        // Le dialogue du back-office porte la croix d'Odoo, et son pied a été retiré pour
        // cela. Une croix de plus ferait de surcroît quitter le back-office pour la
        // boutique — le seul geste que ce dialogue existe pour éviter.
        const ACTION = readFileSync(
            join(__dirname, "..", "src", "page", "configurator_action.xml"), "utf8");
        expect(ACTION).toContain('closable="false"');
        const bloc = SOURCE.slice(SOURCE.indexOf("get canClose()"),
                                  SOURCE.indexOf("onCloseClick()"));
        expect(bloc).toContain("this.props.closable === false");
    });

    test("⚠️ l'HISTORIQUE ne referme pas une page atteinte par navigation", () => {
        // `history.back()` y retomberait sur `/configurator/start/<produit>`, qui crée une
        // configuration NEUVE et renvoie ici : une boucle, pas une sortie. C'est pour cela
        // que le serveur donne l'URL du produit.
        const bloc = SOURCE.slice(SOURCE.indexOf("onCloseClick()"),
                                  SOURCE.indexOf("// ── Libellés"));
        expect(bloc).not.toContain("history");
    });
});

describe("la hauteur de la page sur un TÉLÉPHONE", () => {
    const SCSS = readFileSync(
        join(__dirname, "..", "src", "page", "configurator_page.scss"), "utf8");

    test("⚠️ `dvh` — sinon le pied de page passe sous la barre du navigateur", () => {
        // `100vh` est la hauteur écran BARRES MASQUÉES : le prix et le bouton tombaient
        // dans une bande que rien ne permettait d'atteindre, le corps étant verrouillé.
        expect(SCSS).toContain("height: 100vh;\n    height: 100dvh;");
    });

    test("le repli `vh` reste — un navigateur sans `dvh` garde ce qu'il avait", () => {
        const i = SCSS.indexOf("height: 100vh;");
        const j = SCSS.indexOf("height: 100dvh;");
        expect(i).toBeGreaterThan(-1);
        expect(j).toBeGreaterThan(i);
    });
});
