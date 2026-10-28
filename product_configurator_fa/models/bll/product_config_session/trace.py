"""Ce qu'exécute `product.config.session` (BLL, D-541)."""
from markupsafe import Markup, escape
from odoo import models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def _configuration_snapshot(self):
        """Ce que la configuration DIT aujourd'hui : `{attribut → libellés}`."""
        self.ensure_one()
        snapshot = {}
        for value in self.value_ids:
            snapshot.setdefault(value.attribute_id, self.env["product.attribute.value"])
            snapshot[value.attribute_id] |= value
        return snapshot

    def _log_configuration_change(self, before, after):
        """La note d'historique — `attribut : ancienne → nouvelle` (D-253).

        ⓘ La forme est celle du suivi natif d'Odoo, mais le mécanisme ne peut
        pas l'être : `mail.tracking.value` ne sait pas suivre un **many2many**,
        et une configuration n'est QUE cela. La note est donc composée ici.

        ⚠️ Un attribut qui n'a pas bougé n'apparaît pas. Une note qui répète
        l'état entier à chaque clic ne se lit plus, donc ne protège plus rien.
        """
        self.ensure_one()
        lignes = []
        for attribute in (set(before) | set(after)):
            avant = before.get(attribute)
            apres = after.get(attribute)
            if avant == apres:
                continue
            lignes.append(
                "<li>%s : <span style='text-decoration: line-through'>%s</span>"
                " → <b>%s</b></li>" % (
                    escape(attribute.name),
                    escape(", ".join(avant.mapped("name")) if avant else "—"),
                    escape(", ".join(apres.mapped("name")) if apres else "—"),
                )
            )
        if not lignes:
            return False
        self._message_log(body=Markup("<ul>%s</ul>") % Markup("".join(lignes)))
        return True

    def _notify_configuration_changed(self):
        """Crochet du DIRECT — vide ici, et c'est voulu.

        Le cœur sait qu'une configuration a changé ; il ne sait pas quelle
        forme la page en attend. `product_configurator_web_3d` s'y branche pour
        diffuser l'état sur le bus.
        """
        return True

    def _trace_configuration_change(self, avant):
        """La note, et le signal aux spectateurs — une seule porte pour les deux."""
        if not avant:
            return
        for record in self:
            if record._log_configuration_change(
                avant.get(record.id, {}), record._configuration_snapshot()
            ):
                record._notify_configuration_changed()
