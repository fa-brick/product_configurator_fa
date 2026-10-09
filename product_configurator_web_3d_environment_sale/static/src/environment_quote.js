/** @odoo-module */
/**
 * environment_quote.js — DEMANDER UN DEVIS depuis l'environnement (W-111, étape 8.5a).
 *
 * Le montage d'un environnement appartient à un devis (E-1) : ce bouton confirme chaque
 * configuration posée et en fait une ligne ; ensuite, il met à jour ce même devis tant qu'il n'est
 * pas commandé (Q-12.4). Une configuration incomplète bloque, et la première s'ouvre dans la barre
 * latérale (Q-12.3).
 */
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { EnvironmentEditor } from "@product_editor_environment/editor/environment_editor";

patch(EnvironmentEditor.prototype, {
    setup() {
        super.setup();
        this.state.quote = null;
        // ⓘ Ce que le bouton vient de dire : `{ ok, text }`, ou rien.
        this.state.quoteNotice = null;
        this.state.quoting = false;
    },

    _load(state) {
        super._load(state);
        this.state.quote = state.quote || null;
    },

    get quoteLabel() {
        return this.state.quote ? _t("Update the quotation") : _t("Ask for a quotation");
    },

    async requestQuote() {
        this.state.quoting = true;
        this.state.quoteNotice = null;
        try {
            const result = await rpc("/environment/quote", { token: this.props.token });
            if (result.quote) {
                this.state.quote = result.quote;
                this.state.quoteNotice = { ok: true, text: _t("Quotation %(name)s is up to date.", { name: result.quote.name }) };
                await this._reloadPlacements();
            } else if (result.error === "login_required") {
                // ⓘ Un devis est celui d'un client : le visiteur se connecte, et son chantier le suit
                // (`_claim_session_environments`).
                window.location.href = `/web/login?redirect=${encodeURIComponent(window.location.pathname)}`;
            } else if (result.error === "incomplete") {
                const first = result.missing[0];
                this.state.quoteNotice = { ok: false, text: result.missing.map((item) =>
                    _t("%(product)s: %(questions)s", { product: item.productName, questions: item.questions.join(", ") })).join(" · ") };
                if (first) this.configure(first.openingId);
            } else {
                this.state.quoteNotice = { ok: false, text: result.message || _t("The quotation could not be updated.") };
            }
        } finally {
            this.state.quoting = false;
        }
    },
});
