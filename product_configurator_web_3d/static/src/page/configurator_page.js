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
import { projectSketchItems } from "@product_editor/engine/builder/project_items";
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
        });
        // ⚠️ UN IDENTIFIANT PAR ONGLET, pas par utilisateur : la même personne
        // peut ouvrir la même configuration deux fois, et c'est bien l'onglet
        // qui conduit. `randomUUID` n'existe QUE dans un contexte sécurisé
        // (https, ou localhost) — sur un site en clair il vaut `undefined`, et
        // l'absence de repli ferait de tout le monde le même porteur.
        this.holder = crypto.randomUUID
            ? crypto.randomUUID()
            : `h-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        onWillStart(async () => {
            this.state.model = toViewModel(await this._call("/configurator/state"));
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
            this.state.model = toViewModel(payload, this.state.model);
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
            this.state.model = toViewModel(next, this.state.model);
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
        // ⚠️ Le modèle PRÉCÉDENT est passé : c'est lui qui permet de garder la définition
        // quand la recette n'a pas changé, donc de ne PAS reconstruire la géométrie pour
        // un changement de couleur (D-191).
        this.state.model = toViewModel(next, this.state.model);
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
        this.state.model = toViewModel(next, this.state.model);
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
