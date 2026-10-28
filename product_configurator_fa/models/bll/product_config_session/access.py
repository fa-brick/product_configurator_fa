"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
import secrets
from datetime import timedelta
from odoo import api, fields, models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    @api.model
    def _session_validity_days(self):
        """Combien de jours un lien de reprise reste valable.

        ⚠️ **Le même paramètre gouverne le ménage** : nettoyer une session plus
        tôt que la promesse faite au visiteur (« ce lien reste valable N jours »)
        serait un défaut visible du client (D-091, D-082).
        """
        return int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("product_configurator_fa.session_gc_days", 90)
        )

    def _ensure_access_token(self):
        """Pose un jeton ALÉATOIRE, distinct du numéro de session — D-091.

        ⚠️ `name` vaut `CS0001`, `CS0002`… : une séquence énumérable. Le donner
        au visiteur laisserait lire les configurations des autres en tapant
        `CS0042` — produit, dimensions, prix, et le client dès que la
        configuration devient un devis. Ce n'est pas un risque théorique.

        Et le contrôle d'accès ne peut pas venir d'ailleurs : un visiteur
        anonyme est l'utilisateur PUBLIC, donc toutes les sessions anonymes
        appartiendraient au même `user_id`. **Le jeton EST l'identité**, ce qui
        rend son imprévisibilité non négociable.
        """
        for session in self:
            if not session.sudo().access_token:
                session.sudo().access_token = secrets.token_urlsafe(32)
        return True

    @api.model
    def _find_by_access_token(self, token):
        """Retrouve une session par son jeton, ou rien — jamais par son numéro."""
        if not token or not isinstance(token, str):
            return self.browse()
        session = (
            self.sudo()
            .with_context(active_test=False)
            .search([("access_token", "=", token)], limit=1)
        )
        if not session:
            return self.browse()
        limit = fields.Datetime.now() - timedelta(days=self._session_validity_days())
        if session.create_date < limit or not session.active:
            # La promesse faite au visiteur est datée : passé l'échéance, le
            # lien ne rend rien plutôt que d'ouvrir une configuration qu'on a
            # pu nettoyer entre-temps.
            return self.browse()
        return session

    # ══ PAS DE FOURCHE — D-253 remplace D-092 ═══════════════════════════
    #
    # ⚠️ Ne pas dupliquer la session reprise par un autre : on la PARTAGE — un interne
    # modifie en direct celle d'un collègue ou d'un client du portail (D-253).
    # ⓘ La protection est l'HISTORIQUE : chaque modification laisse sa note
    # `attribut : ancienne → nouvelle` (D-253).
    @api.autovacuum
    def _gc_config_sessions(self):
        """Archive les sessions abandonnées — D-082.

        ⚠️ Le crochet se prend par le DÉCORATEUR en Odoo 18, pas par le nom
        ([[L-137]]). Et le critère n'est pas seulement l'âge : une session
        confirmée, ou qui a donné une variante, a servi — on n'y touche pas.
        """
        limit = fields.Datetime.now() - timedelta(days=self._session_validity_days())
        abandoned = self.sudo().search(
            [
                ("state", "=", "draft"),
                ("product_id", "=", False),
                ("create_date", "<", limit),
            ]
        )
        abandoned.write({"active": False})

    def get_session_search_domain(self, product_tmpl_id, state="draft", parent_id=None):
        """Return domain to search session linked to given
        product template and current login user"""
        domain = [
            ("product_tmpl_id", "=", product_tmpl_id),
            ("user_id", "=", self.env.uid),
            ("state", "=", state),
        ]
        if parent_id:
            domain.append(("parent_id", "=", parent_id))
        return domain

    def get_session_vals(self, product_tmpl_id, parent_id=None, user_id=None):
        """Return the values for creating session"""
        if not user_id:
            user_id = self.env.user.id
        vals = {"product_tmpl_id": product_tmpl_id, "user_id": user_id}
        if parent_id:
            vals.update(parent_id=parent_id)
        return vals

    def search_session(self, product_tmpl_id, parent_id=None):
        domain = self.get_session_search_domain(
            product_tmpl_id=product_tmpl_id, parent_id=parent_id
        )
        session = self.search(domain, order="create_date desc", limit=1)
        return session

    def create_get_session(
        self, product_tmpl_id, parent_id=None, force_create=False, user_id=None
    ):
        if not force_create:
            session = self.search_session(
                product_tmpl_id=product_tmpl_id, parent_id=parent_id
            )
            if session:
                return session
        vals = self.get_session_vals(
            product_tmpl_id=product_tmpl_id,
            parent_id=parent_id,
            user_id=user_id,
        )
        return self.create(vals)
