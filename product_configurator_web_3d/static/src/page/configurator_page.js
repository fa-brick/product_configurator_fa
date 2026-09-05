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
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { PartViewer3D } from "@product_editor/components/part_viewer_3d/part_viewer_3d";
import { projectSketchItems } from "@product_editor/engine/builder/project_items";
import { toViewModel, answerFor, reasonFor, confirmError }
    from "@product_configurator_web_3d/configurator_state";

export class ConfiguratorPage extends Component {
    static template = "product_configurator_web_3d.ConfiguratorPage";
    static components = { PartViewer3D };
    static props = {
        token: { type: String },
    };

    setup() {
        this.state = useState({ model: null, loading: true, reason: null });
        onWillStart(async () => {
            this.state.model = toViewModel(await this._call("/configurator/state"));
            this.state.loading = false;
        });
    }

    _call(route, params = {}) {
        return rpc(route, { token: this.props.token, ...params });
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
    async onPick(questionId, value) {
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
