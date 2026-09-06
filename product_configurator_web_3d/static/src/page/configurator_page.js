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
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { PartViewer3D } from "@product_editor/components/part_viewer_3d/part_viewer_3d";
import { projectSketchItems, projectAssemblyPieces, worldByNodeId }
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
        });
        this._worlds = new Map();
        // ⚠️ UN IDENTIFIANT PAR ONGLET, pas par utilisateur : la même personne
        // peut ouvrir la même configuration deux fois, et c'est bien l'onglet
        // qui conduit. `randomUUID` n'existe QUE dans un contexte sécurisé
        // (https, ou localhost) — sur un site en clair il vaut `undefined`, et
        // l'absence de repli ferait de tout le monde le même porteur.
        this.holder = crypto.randomUUID
            ? crypto.randomUUID()
            : `h-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        onWillStart(async () => {
            await this._applyModel(await this._call("/configurator/state"));
            this.state.loading = false;
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
        const precedent = this.state.model;
        const model = toViewModel(payload, precedent);
        this.state.model = model;
        const memeRecette = precedent && model.definition === precedent.definition;
        const memesValeurs = precedent
            && JSON.stringify(model.scope) === JSON.stringify(precedent.scope);
        if (!memeRecette || !memesValeurs) {
            await this._buildScene(model.definition, model.scope);
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
    async _buildScene(definition, scope) {
        if (!definition) {
            this.state.pieces = [];
            this._worlds = new Map();
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
            const tree = build(
                buildable, scope || {},
                (node, nodeScope, wt) => buildPart(THREE, node, nodeScope, wt, { CSG }),
                { THREE },
            );
            this._worlds = worldByNodeId(tree);
            this.state.pieces = projectAssemblyPieces(buildable, tree);
            this.state.sceneSerial++;
            this._settleCamera();
        } catch (e) {
            // ⚠️ **LE REPLI EST MUET, ET C'EST CE QUI LE REND DANGEREUX** — la leçon est
            // celle de l'éditeur ([[L-188]]) : sans arbre résolu, le viewer redessine
            // depuis les seuls items de la racine. Il montre une pièce PLAUSIBLE, et rien
            // ne dit qu'elle est fausse. On le DIT donc au moins dans la console.
            console.warn("[configurateur] la scène n'a pas pu être construite :", e);
            this.state.pieces = [];
            this._worlds = new Map();
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
        const vue = this.state.model?.camera;
        if (vue && !this.state.ready) {
            this.state.cameraApply = {
                ...vue, move: true, instant: true,
                serial: (this.state.cameraApply?.serial ?? 0) + 1,
            };
        }
        this.state.ready = true;
    }

    /** Un perçage ou une fusion quelque part dans l'arbre ? (D-038) */
    _hasBoolean(node) {
        if (!node) return false;
        const actif = (f) => f.op === "cut" || booleanModeOf(f) !== "none";
        return (node.functions3d || []).some(actif)
            || (node.children || []).some((child) => this._hasBoolean(child));
    }

    /** `Map(nodeId → worldTransform)` — le viewer POSE les enfants avec. */
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
        const refus = confirmError(next);
        if (refus) {
            this.state.reason = refus;
            return;
        }
        this.state.reason = null;
        await this._applyModel(next);
    }

    // ── Libellés — remontés du gabarit, où `_t()` n'est pas résoluble ────────
    get priceLabel() { return _t("Price"); }
    get closedLabel() {
        return _t("This configuration is confirmed and can no longer be changed.");
    }
    get emptyLabel() { return _t("This product asks no question."); }
    get confirmLabel() { return _t("Confirm"); }
}

// Le service de composants publics d'Odoo 18 monte tout `<owl-component name="…">`
// présent dans la page (`web/static/src/public/public_component_service.js`).
registry.category("public_components")
    .add("product_configurator_web_3d.ConfiguratorPage", ConfiguratorPage);
