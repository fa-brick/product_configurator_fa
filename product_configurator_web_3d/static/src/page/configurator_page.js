/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
/**
 * configurator_page.js — La page publique du configurateur (lot 6, D-090).
 *
 * **Le viewer à gauche, les questions à droite** (arbitrage Gerry, 2026-08-26). Page NUE :
 * ni menus ni éditeur de site — `web.frontend_layout` suffit, et le module ne dépend donc
 * pas de `website`.
 *
 * ─ Ce que ce composant fait, et ce qu'il ne fait PAS ─────────────────────────
 *
 * Il **monte et branche**. Toute la logique — ce qu'on affiche, ce qu'on refuse de cliquer,
 * quand la 3D doit se reconstruire — vit dans `configurator_state.js`, qui est **pur et
 * éprouvé** (15 tests). C'est le partage que le blocage n° 4 du lot 6 imposait : sans
 * navigateur ici, ce qui n'est pas pur n'est pas vérifiable.
 *
 * ⚠️ **Le jeton entre par l'URL et ne ressort pas.** Il est passé en prop par le gabarit,
 * employé dans les appels, et n'apparaît dans aucun état rendu (D-190).
 */
import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { PartViewer3D } from "@product_editor/components/part_viewer_3d/part_viewer_3d";
import { projectSketchItems } from "@product_editor/engine/builder/project_items";
import { toBuildable } from "@product_editor/engine/builder/to_buildable";
// ⚠️ **LE PASSAGE OBLIGÉ (D-329).** La page n'appelle plus `build()` : la session charge
// THREE et la CSG (si la recette le demande), tient la graine, met l'allègement dans la
// clé et rend les projections. Six réglages que cette page rejouait de mémoire — et dont
// deux lui ont manqué pendant des mois (≈ 1 s par clic, image identique) ([[L-270]]).
import { createBuildSession } from "@product_editor/engine/builder/build_session";
import { createChronicle } from "@product_editor/engine/builder/build_chronicle";
import { getThree } from "@product_editor/engine/three/three_init";
import { getCSG } from "@product_editor/engine/three/csg_init";
import { getGLTFLoader, getDRACOLoader, DRACO_DECODER_PATH }
    from "@product_editor/engine/three/loaders_init";
// ⚠️ Le MÊME lecteur de fichier cuit que l'éditeur : la page avait le sien, dont les corps
// ne portaient pas le drapeau `baked` — ni la session ni `bakedSolidsByNode` ne les
// auraient reconnus.
import { bakedSolidsFromScene } from "@product_editor/engine/three/baked_scene";
import { toViewModel, answerFor, reasonFor, confirmError, handState, handMessage,
         placementOf, selectableNodeIds, answerForPlacement }
    from "@product_configurator_web_3d/configurator_state";
// Le sous-arbre d'une pose, par la parenté que le moteur publie (D-331) — pour l'ISOLER.
import { subtreeOf } from "@product_editor/engine/builder/project_items";

// Fenêtre de partage de la caméra. 150 ms : sous le seuil où un mouvement
// paraît saccadé à qui regarde, au-dessus de la cadence d'une orbite au doigt.
const CAMERA_SHARE_MS = 150;

export class ConfiguratorPage extends Component {
    static template = "product_configurator_web_3d.ConfiguratorPage";
    static components = { PartViewer3D };
    static props = {
        token: { type: String },
        // ⓘ L'état DÉJÀ PRIS, quand quelqu'un l'a demandé avant nous : la fiche
        // produit le fait pendant que le visiteur lit (route `/configurator/prepare`).
        // Sans lui, la page le demande elle-même — c'est le cas du lien reçu par
        // courriel, qui arrive sans rien de préparé.
        initialState: { type: Object, optional: true },
        // ⓘ Le contexte BOUTIQUE : le geste qui termine met au panier, et le dit.
        // Ailleurs — un lien reçu par courriel, une ligne de devis — terminer reste
        // terminer : il n'y a pas de panier où aller.
        cart: { type: Boolean, optional: true },
        // ⓘ **QUI ACCUEILLE reprend la main à la fin** — le dialogue d'un devis,
        // qui doit poser la variante sur sa ligne et se refermer (D-259). Absent
        // sur une page pleine : il n'y a personne à qui rendre la main.
        onConfirmed: { type: Function, optional: true },
        // ⓘ **LA SORTIE DE L'HÔTE, quand il en a une.** L'overlay de la boutique referme
        // par l'HISTORIQUE — c'est lui la source de vérité, l'URL ne doit jamais mentir sur
        // ce que l'écran montre. Absent, la page cherche sa sortie dans l'état.
        onClose: { type: Function, optional: true },
        // ⚠️ **L'HÔTE QUI A DÉJÀ UN CADRE LE DIT ICI.** Le dialogue du back-office porte la
        // croix d'Odoo — son pied a même été retiré pour cela (*« le Ok est inutile car la
        // croix est présente »*, Gerry, 2026-09-07). Sans ce démenti, la page en dessinerait
        // une SECONDE par-dessus, et celle-ci ferait quitter le back-office pour la
        // boutique. ⓘ Le défaut par défaut est de DESSINER : la page sans hôte — celle du
        // lien reçu — est justement celle qui n'a personne pour la fermer.
        closable: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({
            model: null, loading: true, reason: null, cameraApply: null,
            // Les ENFANTS de l'assemblage, et le compteur qui dit au viewer que
            // les poses ont changé (il ne relit pas une Map par référence).
            pieces: [], sceneSerial: 0,
            // ⚠️ **LES PASSES FINALES — gravures et perforations — MANQUAIENT ICI**, et sept
            // gravures du JeNo étaient invisibles sur cette page, sans une erreur (relevé
            // du 2026-09-22). Le moteur les publie désormais avec l'arbre (D-330) ; la
            // page ne fait que les passer au viewer.
            postBuild: { byNode: {}, byPiece: {}, perforations: {} },
            // ── LA SÉLECTION (D-333) ──────────────────────────────────────────
            // Une seule pose à la fois ; `isolated` quand un double clic l'a ouverte
            // seule. Le SURVOL, lui, ne passe pas par la page : le viewer contoure en
            // orange ce qu'un clic pourrait désigner, comme dans l'éditeur, et ne nomme
            // rien (arbitrage Gerry, 2026-09-23).
            selection: { nodeId: null, isolated: false },
            // ⚠️ FAUX tant que la première scène n'est pas construite : c'est ce qui
            // tient la photo devant. Il ne repasse jamais à faux ensuite — une
            // reconstruction n'est pas une attente, c'est une mise à jour, et
            // recouvrir la 3D à chaque clic la ferait clignoter.
            ready: false,
            // ⓘ **CE QUE LE DOIGT DÉSIGNE dans la 3D** — voir `onSelectPiece`. `null` tant
            // que rien n'est touché, et le vide y ramène : on désigne une pièce, on ne
            // s'engage à rien.
        });
        this._worlds = new Map();
        this._solids = new Map();
        this._bakedSolids = new Map();
        // ⚠️ **LA SESSION DE CONSTRUCTION (D-329)** — possédée par la page, donc par un
        // objet à durée de vie connue : c'est elle qui tient la graine de partage (ce qui
        // évite de reconstruire DOUZE pièces pour en changer une — mesuré le 2026-09-22
        // sur le JeNo : 2 742 ms sans graine, 1 616 ms avec), et qui décide seule de
        // charger la lib CSG. La page ne rejoue plus aucun de ces réglages.
        this._session = createBuildSession({ getThree, getCSG });
        // ⚠️ UN IDENTIFIANT PAR ONGLET, pas par utilisateur : la même personne
        // peut ouvrir la même configuration deux fois, et c'est bien l'onglet
        // qui conduit. `randomUUID` n'existe QUE dans un contexte sécurisé
        // (https, ou localhost) — sur un site en clair il vaut `undefined`, et
        // l'absence de repli ferait de tout le monde le même porteur.
        this.holder = crypto.randomUUID
            ? crypto.randomUUID()
            : `h-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        // ⚠️ **`onWillStart` NE CONSTRUIT PAS LA SCÈNE, et c'est tout l'objet de
        // l'attente.** OWL ne peint RIEN tant que ce crochet n'est pas résolu :
        // y attendre le moteur — une à deux secondes sur un assemblage — laissait
        // la page blanche, puis la faisait apparaître finie. Ni photo, ni
        // tourniquet : l'attente qu'on avait écrite ne s'est jamais vue
        // (constat de Gerry, 2026-09-06).
        //
        // ⓘ On ne prend donc ici que l'ÉTAT — un aller-retour court, et il porte
        // l'image. Le premier rendu montre la photo ; le moteur travaille après.
        onWillStart(async () => {
            const payload = this.props.initialState
                || await this._call("/configurator/state");
            this.state.model = toViewModel(payload);
            // ⚠️ **LA VUE PAR DÉFAUT SE DEMANDE ICI**, avant même le premier rendu :
            // le viewer reçoit alors la pose dans ses props d'origine et se pose
            // dessus sans jamais cadrer par lui-même. Demandée après la construction,
            // elle arrivait 2,5 s trop tard et l'on voyait la pièce à deux endroits
            // (sonde du 2026-09-07).
            //
            // ⚠️ Ce chemin ne passe PAS par `_applyModel` — le premier chargement pose
            // l'état lui-même. Poser la demande dans le seul `_applyModel` revenait à
            // ne jamais l'appliquer au premier affichage, qui est justement celui qui
            // compte.
            this._settleCamera();
            this.state.loading = false;
        });
        // ⓘ APRÈS le montage, et sans `await` : la construction ne bloque plus
        // personne, et c'est elle qui lèvera `ready` en se posant sur la vue.
        onMounted(() => {
            const model = this.state.model;
            if (model && !model.error) {
                this._buildScene(model.definition, model.scope, model.baked);
            } else {
                this.state.ready = true;
            }
        });
        this._listenToOthers();
    }

    /**
     * Suivre EN DIRECT ce que les autres font de cette configuration — D-253.
     *
     * Un commercial reprend la configuration de son client pendant qu'il la regarde :
     * ce qu'il change apparaît chez le client sans qu'il ait à recharger. C'est la
     * contrepartie de la fourche supprimée — on partage, donc on montre.
     *
     * ⚠️ **L'écho de sa PROPRE modification revient aussi**, et on l'applique comme
     * les autres. C'est sans effet : le message porte l'état complet du serveur, qui
     * est justement celui qu'on vient d'appliquer. Filtrer l'auteur coûterait un
     * identifiant de plus sur le fil, pour rien.
     */
    _listenToOthers() {
        const bus = useService("bus_service");
        const channel = `product.config.session_${this.props.token}`;
        const onRemote = (payload) => {
            // ⓘ Le même chemin que la réponse d'un clic : le modèle PRÉCÉDENT est
            // passé, donc la définition est conservée quand la recette n'a pas
            // changé — un spectateur ne reconstruit pas sa géométrie pour une
            // couleur (D-191).
            this._applyModel(payload);
        };
        /**
         * Le point de vue de celui qui conduit — D-256.
         *
         * ⚠️ **On ignore sa PROPRE caméra**, et c'est indispensable : la
         * réappliquer relancerait `onCameraPose`, qui rediffuserait, et la vue
         * se mettrait à trembler entre deux poses presque identiques.
         */
        const onCamera = ({ holder, pose }) => {
            if (!pose || holder === this.holder) return;
            this.state.cameraApply = {
                move: true, pose,
                // ⓘ Une RÉFÉRENCE neuve à chaque fois : le viewer applique la vue
                // quand la prop change d'identité, pas quand son contenu diffère.
                serial: (this.state.cameraApply?.serial ?? 0) + 1,
            };
        };
        /** La sélection de celui qui conduit — partagée comme sa caméra (D-333). */
        const onSelection = ({ holder, nodeId, isolated }) => {
            if (holder === this.holder) return;                    // son propre écho
            this._select(nodeId || null, !!isolated, { broadcast: false });
        };
        bus.addChannel(channel);
        bus.subscribe("configurator_state", onRemote);
        bus.subscribe("configurator_camera", onCamera);
        bus.subscribe("configurator_selection", onSelection);
        // Échap désélectionne — en phase de CAPTURE : un service de raccourcis peut
        // avaler les écoutes en phase bulle ([[L-005]]).
        const onKey = (ev) => { if (ev.key === "Escape" && this.state.selection.nodeId) this.onClearSelection(); };
        document.addEventListener("keydown", onKey, true);
        onWillUnmount(() => {
            bus.unsubscribe("configurator_state", onRemote);
            bus.unsubscribe("configurator_camera", onCamera);
            bus.unsubscribe("configurator_selection", onSelection);
            bus.deleteChannel(channel);
            document.removeEventListener("keydown", onKey, true);
        });
    }

    _call(route, params = {}) {
        // ⓘ Le porteur accompagne le jeton sur TOUS les appels : les routes qui
        // s'en moquent l'ignorent, et aucune ne peut l'oublier.
        return rpc(route, { token: this.props.token, holder: this.holder, ...params });
    }

    /**
     * Poser un nouvel état — et ne reconstruire QUE si la scène en dépend.
     *
     * ⚠️ Un seul endroit remplace le modèle : le premier chargement, un clic, une
     * confirmation, une prise de main et une modification VENUE D'AILLEURS y passent
     * tous. Reconstruire à quatre endroits, c'est en oublier un.
     *
     * ⓘ La DÉFINITION se compare par référence — `toViewModel` garde la précédente
     * quand la recette n'a pas changé (D-191) —, la PORTÉE par valeur : elle arrive du
     * serveur en objet neuf à chaque réponse, et c'est elle qui porte les cotes.
     */
    async _applyModel(payload) {
        const previous = this.state.model;
        const model = toViewModel(payload, previous);
        this.state.model = model;
        // ⚠️ La caméra se demande MAINTENANT, pas après la construction : le viewer la
        // met en attente tant que sa scène n'existe pas, et la sert au premier instant
        // possible. C'est ce qui fait coïncider la 3D et la photo (D-115).
        this._settleCamera();
        const sameRecipe = previous && model.definition === previous.definition;
        const sameValues = previous
            && JSON.stringify(model.scope) === JSON.stringify(previous.scope);
        if (!sameRecipe || !sameValues) {
            await this._buildScene(model.definition, model.scope, model.baked);
        }
    }

    /**
     * CONSTRUIRE la scène — le moteur, pas seulement la projection (D-257).
     *
     * ⚠️ **Un produit réel est un ASSEMBLAGE.** Sa géométrie est dans ses enfants ; la
     * racine ne porte presque rien. Projeter la seule racine donnait un viewer VIDE, sans
     * une erreur — trouvé à l'écran sur le JeNo, jamais par un test.
     *
     * Le viewer n'accepte des enfants qu'accompagnés de leurs POSES, et celles-ci ne se
     * lisent nulle part : elles se CALCULENT. D'où le moteur, ici, dans la page — le
     * même que celui de l'éditeur, au même appel près.
     *
     * ⓘ Tout est déjà dans le bundle public : le sous-bundle `_viewer3d` porte
     * `to_buildable`, `build` et `build_part` depuis D-189. Il ne manquait que le
     * chaînage.
     */
    /**
     * Charger les GLB des pièces DÉJÀ CUITES — avant la construction, jamais pendant.
     *
     * ⓘ **Un échec ne coûte qu'une reconstruction.** Une cuisson est un confort : si le
     * fichier manque ou ne se décode pas, la table reste vide pour ce nœud et le moteur
     * bâtit comme il l'a toujours fait. On le CONSIGNE — un gain qui disparaît en silence
     * ne se diagnostique pas — mais on ne retient pas la page pour autant.
     *
     * ⓘ Le décodeur Draco n'est chargé que s'il y a quelque chose à décoder : une page
     * sans pièce cuite ne doit pas payer son téléchargement.
     */
    async _loadBaked(baked) {
        const loaded = new Map();
        const entries = Object.entries(baked || {});
        if (!entries.length) return loaded;
        try {
            const { GLTFLoader } = await getGLTFLoader();
            const { DRACOLoader } = await getDRACOLoader();
            const decoder = new DRACOLoader().setDecoderPath(DRACO_DECODER_PATH);
            const loader = new GLTFLoader().setDRACOLoader(decoder);
            await Promise.all(entries.map(async ([nodeId, entry]) => {
                try {
                    const response = await fetch(`/web/content/${entry.attachmentId}`);
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    const buffer = await response.arrayBuffer();
                    const gltf = await new Promise((resolve, reject) =>
                        loader.parse(buffer, "", resolve, reject));
                    // ⚠️ La FORME que le moteur attend — `Map(nodeId → {solids})`, la même
                    // que l'éditeur dépose : c'est par elle que `buildPart` sert la pièce
                    // cuite, et que la session la met dans la clé de partage.
                    const solids = bakedSolidsFromScene(this._session.THREE, gltf.scene,
                                                        { faces: entry.faces || {} });
                    if (solids.length) loaded.set(nodeId, { solids });
                } catch (error) {
                    console.warn(`[configurateur] pièce cuite ${nodeId} non chargée :`,
                                 error);
                }
            }));
        } catch (error) {
            console.warn("[configurateur] les pièces cuites n'ont pas pu être lues :",
                         error);
        }
        return loaded;
    }

    async _buildScene(definition, scope, baked = null) {
        if (!definition) {
            this.state.pieces = [];
            this.state.postBuild = { byNode: {}, byPiece: {}, perforations: {} };
            this._worlds = new Map();
            this._solids = new Map();
            this._bakedSolids = new Map();
            this.state.ready = true;
            return;
        }
        try {
            const buildable = toBuildable(definition);
            // ⓘ La session charge THREE, et la lib de booléens SEULEMENT si un perçage ou
            // une fusion existe dans l'arbre (D-038) — la page ne pose plus la question,
            // donc ne peut plus la poser faux.
            await this._session.prepare(buildable);
            // ⚠️ **LES FICHIERS D'ABORD, LA CONSTRUCTION ENSUITE** — `build()` est
            // SYNCHRONE, et charger un fichier ne l'est pas. On remplit donc la table
            // avant, et la session ne fait plus que la consulter.
            const bakedParts = await this._loadBaked(baked);
            // ⓘ Le moteur se mesure PENDANT qu'il construit ([[D-094]]) : le relevé est
            // gardé sur la page, pour une sonde — jamais envoyé, une durée est une
            // propriété de la machine.
            const chronicle = createChronicle();
            const { worlds, solids, baked: bakedSolids, pieces, postBuild } =
                this._session.build(buildable, scope || {}, { bakedParts, chronicle });
            this._lastBuild = chronicle.snapshot();
            this._worlds = worlds;
            // ⚠️ **LES VOLUMES DU MOTEUR** — percés, chanfreinés, fusionnés. Le viewer
            // sait refaire une extrusion depuis son dessin, mais pas ceux-là : ils
            // n'existent que dans l'arbre résolu. Sans cette table, la plaque
            // s'affichait sans ses trous ni ses chanfreins, et rien ne le disait
            // (Gerry, 2026-09-07).
            this._solids = solids;
            // ⚠️ **LES CORPS CUITS, À PART** : une géométrie cuite est déjà dans le repère
            // de la pièce ; montée par la route des esquisses, elle recevrait la matrice
            // du plan une seconde fois — un quart de tour (mesuré sur le bras, 2026-09-19).
            this._bakedSolids = bakedSolids;
            this.state.pieces = pieces;
            this.state.postBuild = postBuild;
            // ⓘ Une permutation peut faire disparaître la pose sélectionnée : la sélection
            // tombe alors, plutôt que de désigner un nœud que personne ne montre.
            const selected = this.state.selection.nodeId;
            if (selected && !pieces.some((p) => p.key === selected)) {
                this._select(null, false, { broadcast: false });
            }
            this.state.sceneSerial++;
            // ⓘ La photo s'efface quand la SCÈNE est là — la caméra, elle, a été
            // demandée dès que l'état est arrivé.
            this.state.ready = true;
        } catch (e) {
            // ⚠️ **LE REPLI EST MUET, ET C'EST CE QUI LE REND DANGEREUX** — la leçon est
            // celle de l'éditeur ([[L-188]]) : sans arbre résolu, le viewer redessine
            // depuis les seuls items de la racine. Il montre une pièce PLAUSIBLE, et rien
            // ne dit qu'elle est fausse. On le DIT donc au moins dans la console.
            console.warn("[configurateur] la scène n'a pas pu être construite :", e);
            this.state.pieces = [];
            this.state.postBuild = { byNode: {}, byPiece: {}, perforations: {} };
            this._worlds = new Map();
            this._solids = new Map();
            this._bakedSolids = new Map();
            // ⚠️ ON DÉCOUVRE QUAND MÊME. Une photo qui ne s'efface jamais laisserait
            // croire à un chargement éternel, alors que la page est vivante et que
            // les questions, elles, répondent.
            this.state.ready = true;
        }
    }

    /**
     * Se poser sur la vue d'où la PHOTO a été prise — puis découvrir la 3D.
     *
     * ⓘ C'est la même vue (`is_thumbnail`, D-115) : « la vue depuis laquelle on veut
     * travailler est la vue que l'on veut montrer ». Le produit se retrouve donc
     * exactement là où l'image le montrait, et le passage de l'une à l'autre ne
     * déplace rien à l'écran.
     *
     * ⚠️ `instant: true` — ARRIVER, pas se déplacer. Une animation raconterait un
     * trajet depuis une pose que personne n'a demandée, et c'est justement ce que
     * l'éditeur a appris à ne plus faire à l'ouverture.
     */
    _settleCamera() {
        // ⚠️ **AVANT LA CONSTRUCTION, ET UNE SEULE FOIS.** Posée après, la vue arrivait
        // 2,5 secondes trop tard : le viewer avait déjà cadré la scène tout seul, et
        // l'on voyait la pièce dans deux positions successives (sonde du 2026-09-07 :
        // cadrage automatique à 2 405 ms, vue par défaut à 4 899 ms). Demandée avant
        // que la scène existe, elle est mise en attente par le viewer et servie au
        // premier instant où il peut — donc jamais après coup.
        const view = this.state.model?.camera;
        if (view && !this._cameraSettled) {
            this._cameraSettled = true;
            this.state.cameraApply = {
                ...view, move: true, instant: true,
                serial: (this.state.cameraApply?.serial ?? 0) + 1,
            };
        }
    }

    /** Les zones de matière, rangées par pièce — ce que le viewer peint. */
    get zonesByPiece() {
        return this.state.model?.zones?.zonesByPiece || {};
    }

    /** `Map(nodeId → worldTransform)` — le viewer POSE les enfants avec. */
    /**
     * Les VOLUMES du moteur, par nœud — ce que le viewer consomme tel quel.
     *
     * ⓘ Même guichet que l'éditeur (`solidsByNodeId`) : deux exemplaires de cette
     * marche divergeraient au premier cas particulier.
     */
    getResolvedSolidsByNodeId() {
        return this._solids || new Map();
    }

    /**
     * Les corps CUITS, par pièce — ce que le viewer monte SANS passer par les esquisses.
     *
     * ⚠️ Cette prop MANQUAIT à la page (relevé du 2026-09-22) : la cuisson n'y arrivant
     * pas (`toViewModel` la laissait tomber), personne ne l'avait vu. Sans elle, un corps
     * cuit repasse par le groupe de son esquisse et reçoit la matrice du plan une seconde
     * fois — le quart de tour mesuré sur le bras du JeNo dans l'éditeur.
     */
    getResolvedBakedSolids() {
        return this._bakedSolids || new Map();
    }

    // ── LA SÉLECTION — D-331 / D-332 / D-333 ──────────────────────────────

    /** Les poses que le client PEUT désigner : celles qui ont des questions à répondre. */
    get selectableNodeIds() {
        // ⓘ Memoïsé sur ses deux entrées : le viewer compare cette prop par identité, et
        // un Set neuf à chaque rendu lui ferait relire la sélection en boucle ([[L-315]]).
        const model = this.state.model, pieces = this.state.pieces;
        if (this._selectableFor?.model !== model || this._selectableFor?.pieces !== pieces) {
            this._selectableFor = { model, pieces, ids: selectableNodeIds(model, pieces) };
        }
        return this._selectableFor.ids;
    }

    /** La pose sélectionnée, sous la forme que le viewer attend — une liste. */
    get selectedNodeIds() {
        const id = this.state.selection.nodeId;
        if (this._selectedFor?.id !== id) this._selectedFor = { id, list: id ? [id] : [] };
        return this._selectedFor.list;
    }

    /** Le placement réglable de la pose sélectionnée — ses questions. */
    get selectedPlacement() {
        const id = this.state.selection.nodeId;
        return id ? placementOf(this.state.model, this.state.pieces, id) : null;
    }

    /**
     * Les pièces que le viewer MONTE : toutes, ou le seul sous-arbre isolé (D-333).
     *
     * ⚠️ **La même référence tant que rien ne change** : le viewer reconstruit sa scène
     * quand cette prop change d'identité ([[L-315]]), et l'isolation ne coûte que cette
     * reconstruction-là — jamais une passe du moteur.
     */
    get viewerPieces() {
        const { nodeId, isolated } = this.state.selection;
        const pieces = this.state.pieces;
        if (!isolated || !nodeId) return pieces;
        if (this._isolatedFor?.pieces !== pieces || this._isolatedFor?.nodeId !== nodeId) {
            const keep = subtreeOf(pieces, nodeId);
            this._isolatedFor = { pieces, nodeId, list: pieces.filter((p) => keep.has(p.key)) };
        }
        return this._isolatedFor.list;
    }

    /** Isolé sur un enfant, la RACINE ne se dessine pas non plus. */
    get viewerSketchItems() {
        const { nodeId, isolated } = this.state.selection;
        return isolated && nodeId ? [] : this.sketchItems;
    }

    /**
     * Un clic dans la 3D — ou dans le vide, qui désélectionne (`null`).
     *
     * ⚠️ **La boucle se REFERME par `selectedNodeIds`** : le viewer n'allume le contour de
     * sélection que par ses props, et sans le retour seul le SURVOL peignait — donc jamais
     * au doigt, qui ne survole pas (relevé de Gerry, 2026-09-22 : « actif sur desktop, pas
     * sur mobile »). Cette boucle remplace celle du 2026-09-22 (`state.selectedNodeId` →
     * `selectedSketchId`), qui allumait tout ce qu'on touchait sans rien en faire.
     *
     * ⚠️ **L'identité voyage TELLE QUELLE** : le viewer rend le `nodeId` de la POSE cliquée,
     * et l'analyser ici allumerait toutes les poses d'un modèle au lieu de celle qu'on a
     * touchée (mesuré dans l'éditeur le 2026-09-13).
     */
    onSelectPiece(nodeId) {
        this._select(nodeId && this.selectableNodeIds.has(nodeId) ? nodeId : null,
                     nodeId ? this.state.selection.isolated : false);
    }

    /** Le double clic : la pièce s'ouvre SEULE, cadrée, son panneau à droite. */
    onActivatePiece(nodeId) {
        if (!nodeId || !this.selectableNodeIds.has(nodeId)) return;
        this._select(nodeId, true);
    }

    /**
     * La flèche de l'en-tête : plus de sélection, plus d'isolation — retour à la racine.
     * ⓘ C'est le SEUL retour : le bouton « voir tout » a été retiré (Gerry, 2026-09-23).
     */
    onClearSelection() {
        this._select(null, false);
    }

    _select(nodeId, isolated, { broadcast = true } = {}) {
        const before = this.state.selection;
        if (before.nodeId === nodeId && before.isolated === isolated) return;
        this.state.selection = { nodeId, isolated };
        this.state.reason = null;
        if (isolated && nodeId) this._frameOn(nodeId);
        // ⚠️ Partagée comme la caméra (D-256) : seul qui tient la main diffuse, et ce
        // qui vient du fil ne se rediffuse pas — sinon deux pages se renverraient la
        // même sélection à tour de rôle.
        if (broadcast && this.hand.mine) {
            this._call("/configurator/select", { node_id: nodeId, isolated });
        }
    }

    /**
     * Cadrer la pose isolée : la cible se déplace sur elle, la distance s'ajuste, les
     * angles restent ceux du moment — on ouvre une pièce, on ne change pas de point de vue.
     */
    _frameOn(nodeId) {
        const pose = this._lastPose || this.state.model?.camera?.pose;
        if (!pose) return;
        this.state.cameraApply = {
            move: true, pose, fitDistance: true, target: { nodeId },
            serial: (this.state.cameraApply?.serial ?? 0) + 1,
        };
    }

    /**
     * Répondre à une question — de la RACINE (`nodeId` nul) ou du PLACEMENT sélectionné.
     *
     * ⓘ Une seule porte pour les deux : ce qui change est le lien qui part avec la
     * réponse, jamais le geste.
     */
    async onAnswer(nodeId, questionId, value) {
        if (!nodeId) return this.onPick(questionId, value);
        if (this.watching) {
            this.state.reason = this.handLabel;
            return;
        }
        const payload = answerForPlacement(this.state.model, this.selectedPlacement, questionId, value.id);
        if (!payload) {
            this.state.reason = reasonFor(value);
            return;
        }
        this.state.reason = null;
        this.state.loading = true;
        const next = await this._call("/configurator/set_value", payload);
        await this._applyModel(next);
        this.state.loading = false;
    }

    /** La liste déroulante d'un placement — même porte que `onSelect` pour la racine. */
    onAnswerSelect(nodeId, question, ev) {
        const chosenId = Number(ev.target.value);
        const value = question.values.find((v) => v.id === chosenId);
        if (value) this.onAnswer(nodeId, question.id, value);
    }

    /**
     * La PIÈCE de la racine — et sans elle, aucune matière sur un produit d'une
     * seule pièce.
     *
     * ⚠️ `projectAssemblyPieces` saute délibérément la racine : dans l'éditeur,
     * c'est la pièce OUVERTE, dessinée par un autre chemin. Ici la racine est le
     * produit : ses items sont rendus avec `rootPieceId`, et les zones de matière
     * sont rangées PAR PIÈCE (D-166). Sans cet identifiant, elles ne trouvent
     * personne — la plaque restait grise.
     */
    /**
     * L'AMBIANCE du produit — l'éclairage sous lequel il se montre.
     *
     * ⓘ `undefined` et non `null` quand il n'y en a pas : la prop du viewer est optionnelle,
     * et dans OWL `optional` autorise une prop ABSENTE, jamais une prop NULLE ([[L-178]]).
     * Un `null` ferait lever la validation le jour où quelqu'un ouvre le mode debug — et
     * l'écran mourrait en emportant son propre diagnostic.
     *
     * ⚠️ Absente, le viewer rend ses constantes mesurées : le produit s'affiche exactement
     * comme avant ce chantier, jamais en noir.
     */
    get ambience() {
        return this.state.model?.ambience || undefined;
    }

    get rootPieceId() {
        return this.state.model?.definition?.model3dId ?? null;
    }

    /** Le nœud de la racine — par lui, le viewer retrouve son volume construit. */
    get rootNodeId() {
        return this.state.model?.definition?.id ?? null;
    }

    getResolvedWorldByNodeId() {
        return this._worlds || new Map();
    }

    /**
     * Les items que le viewer consomme — projetés de la DÉFINITION.
     *
     * ⚠️ La projection est celle de l'éditeur, **partagée** depuis le 2026-08-26 : en
     * écrire une seconde ici aurait donné deux lectures d'une même donnée, dont une seule
     * serait corrigée le jour où la forme d'un nœud change.
     */
    get sketchItems() {
        const model = this.state.model;
        if (!model?.definition) return [];
        return projectSketchItems(model.definition, model.scope || {});
    }

    get questions() {
        return this.state.model?.questions || [];
    }

    /** Le prix, tel qu'il se lit — une somme, pas un détail (D-176). */
    get price() {
        return this.state.model?.price || 0;
    }

    reasonFor(value) {
        return reasonFor(value);
    }

    /**
     * Répondre à une question.
     *
     * ⚠️ **Un appui sur une valeur éteinte n'est pas ignoré : il DIT pourquoi** (D-178).
     * C'est le seul geste qui vaille sur les deux mondes — un clic au bureau, une tape sur
     * un téléphone — et c'est pour cela qu'une valeur indisponible reste cliquable.
     */
    /** Qui conduit, vu d'ici. */
    get hand() {
        return handState(this.state.model, this.holder);
    }

    /** Ce qui est en LECTURE SEULE parce qu'un autre conduit. */
    get watching() {
        const hand = this.hand;
        return !hand.free && !hand.mine;
    }

    get handLabel() {
        return handMessage(this.hand);
    }

    get takeHandLabel() { return _t("Take over"); }
    get backToProductLabel() { return _t("Back to product"); }
    /**
     * Prendre la main — et le dire à ceux qui regardent.
     *
     * ⓘ Cela réussit toujours (D-255) : ce n'est pas un verrou qu'on force,
     * c'est une conduite qu'on annonce.
     */
    async onTakeHand() {
        this.state.loading = true;
        const next = await this._call("/configurator/take_hand");
        this.state.loading = false;
        if (next && !next.error) {
            this.state.reason = null;
            await this._applyModel(next);
        }
    }

    /**
     * Publier son point de vue — seulement si l'on conduit.
     *
     * ⚠️ Le viewer débruite déjà (il n'émet qu'au-delà d'un degré ou d'un
     * millimètre), mais une orbite au doigt en produit tout de même des
     * dizaines par seconde. On garde le DERNIER d'une fenêtre plutôt que de
     * tous les envoyer : ce qui compte est où l'on s'arrête, pas le trajet.
     */
    onCameraPose(pose) {
        if (!pose) return;
        // Retenue pour tous : c'est la pose d'où l'on cadrera une pièce isolée.
        this._lastPose = pose;
        if (!this.hand.mine) return;
        if (this._poseTimer) return;
        this._poseTimer = browser.setTimeout(() => {
            this._poseTimer = null;
            this._call("/configurator/camera", { pose: this._lastPose });
        }, CAMERA_SHARE_MS);
    }

    /**
     * Répondre par une LISTE DÉROULANTE.
     *
     * ⓘ Le geste rejoint `onPick` — une seule porte pour toutes les formes. Ce qui
     * change d'une forme à l'autre est ce que l'œil reçoit, jamais ce qui part au
     * serveur.
     *
     * ⚠️ `ev.target.value` est une CHAÎNE : la comparer telle quelle aux
     * identifiants numériques ne trouverait jamais rien, et la question resterait
     * muette sans qu'aucune erreur ne le dise.
     */
    onSelect(question, ev) {
        const chosenId = Number(ev.target.value);
        const value = question.values.find((v) => v.id === chosenId);
        if (value) this.onPick(question.id, value);
    }

    async onPick(questionId, value) {
        // ⚠️ Le refus est LOCAL avant d'être serveur : le serveur refuse aussi
        // (c'est lui qui fait foi), mais laisser partir l'appel ferait clignoter
        // la page pour finir sur le même message.
        if (this.watching) {
            this.state.reason = this.handLabel;
            return;
        }
        const payload = answerFor(this.state.model, questionId, value.id);
        if (!payload) {
            this.state.reason = reasonFor(value);
            return;
        }
        this.state.reason = null;
        this.state.loading = true;
        const next = await this._call("/configurator/set_value", payload);
        await this._applyModel(next);
        this.state.loading = false;
    }

    /**
     * Terminer la configuration.
     *
     * ⚠️ Un refus n'efface RIEN. Il manque une réponse : la page reste telle quelle
     * et dit laquelle. Seule une réussite remplace l'état — et la session étant alors
     * close, le bandeau de fermeture prend la place du bouton, sans code de plus.
     */
    async onConfirm() {
        this.state.loading = true;
        const next = await this._call("/configurator/confirm");
        this.state.loading = false;
        const refusal = confirmError(next);
        if (refusal) {
            this.state.reason = refusal;
            return;
        }
        this.state.reason = null;
        await this._applyModel(next);
        // ⚠️ APRÈS `_applyModel` : c'est lui qui pose la variante née de la
        // confirmation dans l'état, et c'est elle que l'hôte attend.
        if (this.props.onConfirmed) {
            this.props.onConfirmed({ productId: this.state.model?.productId });
            return;
        }
        await this._addToCart();
    }

    /**
     * Mettre la configuration au panier — le geste qui la fait exister ailleurs.
     *
     * ⚠️ **APRÈS la confirmation, jamais avant** : c'est elle qui fait naître la
     * variante, et il n'y a rien à mettre au panier tant qu'elle n'existe pas.
     *
     * ⓘ Un échec ici ne défait RIEN : la configuration est confirmée, sa variante
     * existe, et son lien la retrouve. On le dit plutôt que de faire comme si le
     * clic n'avait pas eu lieu.
     */
    async _addToCart() {
        if (!this.props.cart) return;
        const productId = this.state.model?.productId;
        if (!productId) return;
        try {
            await rpc("/shop/cart/update_json", { product_id: productId, add_qty: 1 });
            browser.location.href = "/shop/cart";
        } catch (e) {
            console.warn("[configurateur] mise au panier impossible :", e);
            this.state.reason = _t(
                "This configuration is confirmed, but the cart could not be updated.");
        }
    }


    /**
     * Y a-t-il une sortie ? — et c'est bien la question, pas « est-on dans un overlay ».
     *
     * ⚠️ **Une page atteinte par NAVIGATION n'a pas d'historique exploitable** : revenir en
     * arrière retombe sur `/configurator/start/<produit>`, qui crée une configuration NEUVE
     * et renvoie ici — une boucle, pas une sortie. Le retour est donc l'URL du PRODUIT, et
     * seul le serveur peut la donner : la route de la page ne résout pas le jeton, et ne
     * doit pas le faire (D-190).
     *
     * ⓘ Rien à afficher quand il n'y a rien à fermer : le dialogue du back-office se ferme
     * par son propre cadre, et un lien mort n'a pas de produit où revenir.
     */
    get canClose() {
        if (this.props.closable === false) return false;
        return !!this.props.onClose || !!this.state.model?.productUrl;
    }

    /** Fermer : rendre la main à l'hôte s'il en a demandé une, sinon revenir au produit. */
    onCloseClick() {
        if (this.props.onClose) {
            this.props.onClose();
            return;
        }
        const url = this.state.model?.productUrl;
        if (url) browser.location.href = url;
    }

    // ── Libellés — remontés du gabarit, où `_t()` n'est pas résoluble ────────
    get priceLabel() { return _t("Price"); }
    get chooseLabel() { return _t("Choose…"); }

    /** Une question est repondue des qu'une de ses valeurs est retenue. */
    isAnswered(question) {
        return question.values.some((value) => value.chosen);
    }

    get closedLabel() {
        return _t("This configuration is confirmed and can no longer be changed.");
    }
    get emptyLabel() { return _t("This product asks no question."); }
    get confirmLabel() {
        return this.props.cart ? _t("Add to cart") : _t("Confirm");
    }
}

// Le service de composants publics d'Odoo 18 monte tout `<owl-component name="…">`
// présent dans la page (`web/static/src/public/public_component_service.js`).
registry.category("public_components")
    .add("product_configurator_web_3d.ConfiguratorPage", ConfiguratorPage);
