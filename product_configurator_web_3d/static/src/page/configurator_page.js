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
import { projectSketchItems, projectAssemblyPieces, solidsByNodeId, worldByNodeId }
    from "@product_editor/engine/builder/project_items";
import { toBuildable } from "@product_editor/engine/builder/to_buildable";
import { build } from "@product_editor/engine/builder/build";
// ⓘ Deux modules voisins et faciles à confondre : `buildPart` — celui qui CONSTRUIT
// une pièce — vit dans `part_descriptor` ; `build_part` porte la lecture des
// fonctions 3D. L'éditeur importe les deux de la même façon.
import { buildPart } from "@product_editor/engine/builder/part_descriptor";
import { booleanModeOf } from "@product_editor/engine/builder/build_part";
import { getThree } from "@product_editor/engine/three/three_init";
import { getCSG } from "@product_editor/engine/three/csg_init";
import { getGLTFLoader, getDRACOLoader, DRACO_DECODER_PATH }
    from "@product_editor/engine/three/loaders_init";
import { bakedPart } from "@product_configurator_web_3d/page/baked_parts";
import { toViewModel, answerFor, reasonFor, confirmError, handState, handMessage }
    from "@product_configurator_web_3d/configurator_state";

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
            // ⚠️ FAUX tant que la première scène n'est pas construite : c'est ce qui
            // tient la photo devant. Il ne repasse jamais à faux ensuite — une
            // reconstruction n'est pas une attente, c'est une mise à jour, et
            // recouvrir la 3D à chaque clic la ferait clignoter.
            ready: false,
            // ⓘ **CE QUE LE DOIGT DÉSIGNE dans la 3D** — voir `onSelectPiece`. `null` tant
            // que rien n'est touché, et le vide y ramène : on désigne une pièce, on ne
            // s'engage à rien.
            selectedNodeId: null,
        });
        this._worlds = new Map();
        // ⚠️ **LA GRAINE — ce qui évite de reconstruire DOUZE pièces pour en changer une.**
        // `build()` repart sans rien : une permutation refaisait donc tout l'arbre, CSG
        // compris, alors qu'une seule pose est neuve. Mesuré le 2026-09-22 sur le JeNo, au
        // travers du serveur d'essai : 2 742 ms sans graine, **1 616 ms avec**, et les
        // douze autres pièces annoncées « semée » à 0 ms. C'est la mécanique que l'éditeur
        // emploie depuis le 2026-09-19 (`model3d_editor.js`), au même appel près.
        //
        // ⓘ `null` au départ, et non une carte vide : la première construction n'a rien à
        // emprunter, et le moteur distingue « pas de graine » de « graine sans rien ».
        this._sharedParts = null;
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
        bus.addChannel(channel);
        bus.subscribe("configurator_state", onRemote);
        bus.subscribe("configurator_camera", onCamera);
        onWillUnmount(() => {
            bus.unsubscribe("configurator_state", onRemote);
            bus.unsubscribe("configurator_camera", onCamera);
            bus.deleteChannel(channel);
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
    async _loadBaked(THREE, baked) {
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
                    loaded.set(nodeId, { scene: gltf.scene, faces: entry.faces || [] });
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
            this._worlds = new Map();
            this._solids = new Map();
            this.state.ready = true;
            return;
        }
        try {
            const buildable = toBuildable(definition);
            const THREE = await getThree();
            // ⓘ La bibliothèque de booléens est LOURDE : on ne la charge que si un
            // perçage ou une fusion existe dans l'arbre (D-038). Sans elle, les volumes
            // sont pleins — ce qui se voit, alors qu'un chargement inutile ne se voit pas.
            const CSG = this._hasBoolean(buildable) ? await getCSG() : null;
            // ⚠️ **LES FICHIERS D'ABORD, LA CONSTRUCTION ENSUITE** — `build()` est
            // SYNCHRONE, et charger un fichier ne l'est pas. On remplit donc la table
            // avant, et le constructeur ne fait plus que la consulter. C'est ce que
            // l'éditeur fait de ses géométries importées, et pour la même raison.
            const loaded = await this._loadBaked(THREE, baked);
            const sharedOut = new Map();
            const tree = build(
                buildable, scope || {},
                // ⓘ **La substitution est une ENVELOPPE, pas une bifurcation.** Un nœud
                // déjà cuit rend sa pièce toute faite ; tout le reste passe par le chemin
                // d'avant, inchangé. Et `bakedPart` rend `null` au moindre doute — une
                // table vide, un fichier sans maille — donc l'incertitude retombe
                // toujours sur la construction.
                (node, nodeScope, wt) => bakedPart(THREE, node, wt, loaded)
                    || buildPart(THREE, node, nodeScope, wt, { CSG }),
                // ⚠️ **CARTE NEUVE EN SORTIE, jamais la graine elle-même.** Ce qui n'a pas
                // servi à cette passe ne repasse pas : c'est ce qui borne le cache à
                // l'arbre courant au lieu de le laisser enfler en retenant des géométries
                // que le viewer croit libérées.
                //
                // ⚠️ **`bakedParts` ENTRE DANS LA CLÉ, et ce n'est pas décoratif.** Une
                // pose servie par son GLB n'a pas la géométrie d'une pose construite, et
                // rien dans sa recette ne le dit. Sans ce drapeau, une pièce cuite à la
                // passe d'avant serait rendue telle quelle à une passe qui, elle, n'a plus
                // son fichier — la géométrie cuite survivrait à sa cuisson.
                { THREE, bakedParts: loaded,
                  sharedSeed: this._sharedParts, sharedOut },
            );
            // ⓘ Retenue APRÈS coup, donc jamais en cas d'échec : une passe qui a levé n'a
            // rien à léguer, et la graine d'avant — dont les clés portent la recette —
            // reste bonne pour la suivante.
            this._sharedParts = sharedOut;
            this._worlds = worldByNodeId(tree);
            // ⚠️ **LES VOLUMES DU MOTEUR** — percés, chanfreinés, fusionnés. Le viewer
            // sait refaire une extrusion depuis son dessin, mais pas ceux-là : ils
            // n'existent que dans l'arbre résolu. Sans cette table, la plaque
            // s'affichait sans ses trous ni ses chanfreins, et rien ne le disait
            // (Gerry, 2026-09-07).
            this._solids = solidsByNodeId(tree);
            this.state.pieces = projectAssemblyPieces(buildable, tree);
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
            this._worlds = new Map();
            this._solids = new Map();
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

    /** Un perçage ou une fusion quelque part dans l'arbre ? (D-038) */
    _hasBoolean(node) {
        if (!node) return false;
        const actif = (f) => f.op === "cut" || booleanModeOf(f) !== "none";
        return (node.functions3d || []).some(actif)
            || (node.children || []).some((child) => this._hasBoolean(child));
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
        if (!this.hand.mine || !pose) return;
        this._lastPose = pose;
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
     * LE CONTOUR — ce qu'un clic, ou une TAPE, vient de désigner dans la scène.
     *
     * ⚠️ **L'aller existait, le retour manquait.** Le viewer publie déjà ce qu'on touche
     * (`onSelectPiece`, nourri aussi bien par la souris que par `onTouchEnd`), mais il
     * n'allume son contour de SÉLECTION que d'après une prop — `selectedSketchId`. La page
     * ne passait ni l'un ni l'autre : le contour cyan n'était donc allumé NULLE PART, ni au
     * bureau ni au téléphone.
     *
     * ⓘ Ce qu'on voyait au bureau était le contour de SURVOL, orange, que le viewer allume
     * tout seul au passage de la souris. **Un doigt ne survole pas** — d'où « ça marche sur
     * desktop et pas sur mobile » (Gerry, 2026-09-22), qui n'était pas une histoire de
     * tactile mais de boucle non refermée. L'éditeur, lui, la referme depuis toujours
     * (`onSelectPiece` → `state.selectedNodeId` → `selectedSketchId`) : c'est pourquoi la
     * sélection y répond au doigt.
     *
     * ⚠️ **L'identité voyage TELLE QUELLE.** Le viewer rend soit le `nodeId` d'un placement
     * (une chaîne), soit un `pieceId` (un nombre) quand la pièce n'a pas de placement, et
     * `_selectedSubtreeGroups` sait lire les deux. L'analyser ici — pour « normaliser » —
     * allumerait toutes les poses d'un modèle au lieu de celle qu'on a touchée, défaut
     * mesuré dans l'éditeur le 2026-09-13.
     *
     * ⓘ `null` arrive quand le clic tombe dans le VIDE : le viewer le publie, et il
     * éteint. C'est le geste attendu, et il ne coûte rien à écrire.
     */
    onSelectPiece(id) {
        this.state.selectedNodeId = id ?? null;
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
