# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Les routes publiques de la configuration — D-091, D-190, lot 6 blocage n° 3.

Ce qui est éprouvé ici est surtout ce qui doit être REFUSÉ : sans cela, un jeton
de 32 octets ne protège rien. Et une chose qui doit **ne pas** arriver — la
fourche à chaque clic, qui ferait perdre sa configuration au visiteur.
"""
import json

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPublicRoutes(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]
        cls.attribute = Attribute.create({"name": "Couleur"})
        cls.blanc, cls.noir = Value.create([
            {"name": "Blanc", "attribute_id": cls.attribute.id},
            {"name": "Noir", "attribute_id": cls.attribute.id},
        ])
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte configurable",
            "config_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.attribute.id,
                "value_ids": [Command.set((cls.blanc | cls.noir).ids)],
            })],
        })
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": cls.tmpl.id,
            "user_id": cls.env.user.id,
            "value_ids": [Command.set(cls.blanc.ids)],
        })

    def _call(self, route, **params):
        """Un appel JSON-RPC anonyme — comme un visiteur, sans session web."""
        response = self.url_open(
            route,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
            headers={"Content-Type": "application/json"},
        )
        return response.json().get("result")

    # ── CE QUI DOIT ÊTRE REFUSÉ ──────────────────────────────────────────

    def test_sans_jeton_rien(self):
        self.assertEqual(self._call("/configurator/state"),
                         {"error": "unknown_session"})

    def test_un_jeton_inconnu_ne_dit_pas_qu_il_est_inconnu(self):
        """⚠️ Même réponse qu'un jeton absent : distinguer « inconnu » de
        « périmé » dirait à qui tâtonne quels jetons ont existé."""
        self.assertEqual(self._call("/configurator/state", token="x" * 32),
                         {"error": "unknown_session"})

    def test_le_NUMÉRO_de_session_ne_vaut_pas_jeton(self):
        """⚠️ `CS0001` est une séquence énumérable — c'est tout le motif de D-091."""
        self.assertEqual(self._call("/configurator/state",
                                    token=self.session.name),
                         {"error": "unknown_session"})

    def test_une_session_ARCHIVÉE_ne_répond_plus(self):
        self.session.active = False
        self.assertEqual(self._call("/configurator/state",
                                    token=self.session.access_token),
                         {"error": "unknown_session"})

    def test_une_session_CONFIRMÉE_ne_se_modifie_plus(self):
        """Elle a donné sa variante : la changer sous une commande passée serait
        pire qu'un refus."""
        self.session.action_confirm()
        out = self._call("/configurator/set_value",
                         token=self.session.access_token,
                         attribute_id=self.attribute.id, value_id=self.noir.id)
        self.assertEqual(out, {"error": "session_closed"})

    def test_une_valeur_d_une_AUTRE_question_est_refusée(self):
        autre = self.env["product.attribute.value"].create({
            "name": "Chêne",
            "attribute_id": self.env["product.attribute"].create({"name": "Bois"}).id,
        })
        out = self._call("/configurator/set_value",
                         token=self.session.access_token,
                         attribute_id=self.attribute.id, value_id=autre.id)
        self.assertEqual(out, {"error": "unknown_value"})

    # ── CE QUI DOIT MARCHER ──────────────────────────────────────────────

    def test_un_jeton_valide_rend_SA_configuration(self):
        state = self._call("/configurator/state", token=self.session.access_token)
        self.assertEqual(state["productName"], "Porte configurable")
        self.assertEqual(len(state["attributes"]), 1)
        choisies = [v["name"] for v in state["attributes"][0]["values"] if v["chosen"]]
        self.assertEqual(choisies, ["Blanc"])

    def test_les_valeurs_INDISPONIBLES_sont_rendues_marquées(self):
        """⚠️ On les grise, on ne les cache pas (D-168) — et un appui dira
        pourquoi (D-178). Les retirer ici ôterait à la page le moyen de le dire."""
        state = self._call("/configurator/state", token=self.session.access_token)
        for value in state["attributes"][0]["values"]:
            self.assertIn("available", value)

    def test_répondre_change_la_configuration_et_rend_l_état(self):
        state = self._call("/configurator/set_value",
                           token=self.session.access_token,
                           attribute_id=self.attribute.id, value_id=self.noir.id)
        choisies = [v["name"] for v in state["attributes"][0]["values"] if v["chosen"]]
        self.assertEqual(choisies, ["Noir"])
        self.assertEqual(self.session.value_ids, self.noir)

    def test_repondre_NE_FORKE_PAS_la_session(self):
        """D-190 — le porteur du jeton EST le propriétaire.

        Ce test valait d'abord contre `_session_for_edit`, qui dupliquait la
        session reprise par un autre. Cette fourche a été RETIRÉE du cœur
        (D-253) : le test garde tout son sens, il garde simplement contre une
        autre récidive — celle où répondre créerait une session par clic.
        """
        avant = self.env["product.config.session"].search_count([])
        self._call("/configurator/set_value", token=self.session.access_token,
                   attribute_id=self.attribute.id, value_id=self.noir.id)
        self.assertEqual(self.env["product.config.session"].search_count([]), avant)
        self.assertFalse(self.session.child_ids)

    def test_le_jeton_ne_RESSORT_pas_de_la_réponse(self):
        """Une page publique ne doit rien laisser filtrer qui permette d'énumérer."""
        state = self._call("/configurator/state", token=self.session.access_token)
        brut = json.dumps(state)
        self.assertNotIn(self.session.access_token, brut)
        self.assertNotIn(self.session.name, brut)

    # ── LA PAGE (lot 6) ──────────────────────────────────────────────────

    def test_la_page_se_rend_pour_un_visiteur_anonyme(self):
        """Elle est NUE : `web.frontend_layout`, sans `website` — et elle porte le
        point de montage du composant."""
        page = self.url_open(f"/configurator/{self.session.access_token}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("product_configurator_web_3d.ConfiguratorPage", page.text)

    def test_la_page_charge_le_bundle_qui_porte_le_VIEWER(self):
        """⚠️ Sans `web.assets_frontend`, la page s'afficherait — vide. C'est le
        blocage n° 2 du lot 6, et il se vérifie ici de bout en bout."""
        page = self.url_open(f"/configurator/{self.session.access_token}")
        self.assertIn("assets_frontend", page.text)

    def test_un_jeton_inconnu_rend_QUAND_MÊME_la_page(self):
        """⚠️ Délibéré (D-190) : c'est l'appel d'état qui dira que le lien ne vaut
        rien. Un 404 ici dirait à qui tâtonne QUELS JETONS EXISTENT."""
        page = self.url_open("/configurator/" + "z" * 32)
        self.assertEqual(page.status_code, 200)

    def test_le_jeton_voyage_en_PROP_et_nulle_part_ailleurs(self):
        page = self.url_open(f"/configurator/{self.session.access_token}")
        # Il est dans le prop du composant — c'est ainsi qu'il entre — et la page ne
        # porte ni le numéro de session ni un autre jeton.
        self.assertIn(self.session.access_token, page.text)
        self.assertNotIn(self.session.name, page.text)


@tagged("post_install", "-at_install")
class TestDisplayShapes(HttpCase):
    """La FORME d'une question, et la règle qu'elle change — 2026-09-06.

    Cinq formes viennent d'Odoo, la sixième — la carte — a été ajoutée pour les
    réponses qui désignent. Une seule change la règle du serveur : la question
    MULTIPLE, dont les réponses s'ajoutent au lieu de se remplacer.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Value = cls.env["product.attribute.value"]
        # Odoo l'exige : une question a cases cochees ne cree pas de variante
        # (contrainte check_multi_checkbox_no_variant).
        cls.options = cls.env["product.attribute"].create({
            "name": "Options",
            "display_type": "multi",
            "create_variant": "no_variant",
        })
        cls.gravure, cls.vernis = Value.create([
            {"name": "Gravure", "attribute_id": cls.options.id},
            {"name": "Vernis", "attribute_id": cls.options.id},
        ])
        cls.tmpl_multi = cls.env["product.template"].create({
            "name": "Porte a options",
            "config_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.options.id,
                "value_ids": [Command.set((cls.gravure | cls.vernis).ids)],
                "multi": True,
            })],
        })
        cls.session_multi = cls.env["product.config.session"].create({
            "product_tmpl_id": cls.tmpl_multi.id,
            "user_id": cls.env.user.id,
        })
        cls.session_multi._ensure_access_token()

    def _call(self, route, **params):
        """Un appel JSON-RPC anonyme — comme un visiteur, sans session web."""
        response = self.url_open(
            route,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
            headers={"Content-Type": "application/json"},
        )
        return response.json().get("result")

    def _answer(self, value):
        return self._call(
            "/configurator/set_value", token=self.session_multi.access_token,
            attribute_id=self.options.id, value_id=value.id,
        )

    def test_la_FORME_est_servie_a_la_page(self):
        """Elle était réglée en back-office et n'arrivait jamais : la page rendait
        un bouton pour tout."""
        state = self._call("/configurator/state", token=self.session_multi.access_token)
        self.assertEqual(state["attributes"][0]["displayType"], "multi")

    def test_le_type_CARTE_existe(self):
        """⚠️ Il n'est pas d'Odoo — ses cinq formes ne montrent aucune image."""
        formes = dict(self.env["product.attribute"]._fields["display_type"].selection)
        self.assertIn("card", formes)

    def test_une_question_MULTIPLE_garde_les_deux_reponses(self):
        self._answer(self.gravure)
        state = self._answer(self.vernis)
        retenues = {v["name"] for v in state["attributes"][0]["values"] if v["chosen"]}
        self.assertEqual(retenues, {"Gravure", "Vernis"})

    def test_re_repondre_DECOCHE_au_lieu_de_ne_rien_faire(self):
        self._answer(self.gravure)
        state = self._answer(self.gravure)
        retenues = [v["name"] for v in state["attributes"][0]["values"] if v["chosen"]]
        self.assertEqual(retenues, [])

    def test_une_question_SIMPLE_remplace_toujours(self):
        """La règle d'avant ne bouge pas — c'est la forme qui décide, pas le hasard."""
        self.tmpl_multi.attribute_line_ids.multi = False
        self._answer(self.gravure)
        state = self._answer(self.vernis)
        retenues = [v["name"] for v in state["attributes"][0]["values"] if v["chosen"]]
        self.assertEqual(retenues, ["Vernis"])


@tagged("post_install", "-at_install")
class TestNumericValueOnThePage(HttpCase):
    """Ce que le CLIENT lit d'un nombre — D-160, demandé le 2026-09-07.

    La valeur rangée est le nombre nu ; partout où elle se LIT, elle porte son
    unité. Le back-office le faisait depuis ce matin, la page non : la même
    largeur se lisait « 2400 mm » d'un côté et « 2400 » de l'autre.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.largeur = cls.env["product.attribute"].create({
            "name": "Largeur",
            "custom_type": "float",
            "uom_id": cls.env.ref("uom.product_uom_millimeter").id,
            "create_variant": "no_variant",
        })
        cls.deux_mille = cls.env["product.attribute.value"].create(
            {"name": "2400", "attribute_id": cls.largeur.id}
        )
        cls.tmpl = cls.env["product.template"].create({
            "name": "Porte a largeur",
            "config_ok": True,
            "attribute_line_ids": [Command.create({
                "attribute_id": cls.largeur.id,
                "value_ids": [Command.set(cls.deux_mille.ids)],
            })],
        })
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": cls.tmpl.id, "user_id": cls.env.user.id,
        })
        cls.session._ensure_access_token()

    def _call(self, route, **params):
        response = self.url_open(
            route,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
            headers={"Content-Type": "application/json"},
        )
        return response.json().get("result")

    def test_la_page_montre_le_nombre_AVEC_son_unité(self):
        state = self._call("/configurator/state", token=self.session.access_token)
        libelles = [v["name"] for a in state["attributes"] for v in a["values"]]
        self.assertEqual(libelles, ["2400 mm"])

    def test_la_valeur_RANGÉE_reste_le_nombre_nu(self):
        """⚠️ L'affichage ne doit rien changer au stockage : « 2400 mm » en base
        serait une valeur distincte de « 2400 » pour la même largeur."""
        self.assertEqual(self.deux_mille.name, "2400")


@tagged("post_install", "-at_install")
class TestTheScopeCarriesNumbers(HttpCase):
    """La portée envoyée à la page porte des NOMBRES, pas des identifiants.

    ⚠️ Relevé de Gerry le 2026-09-07, mesuré : `scope = {'__attribute_144': 292.0}`
    — 292 étant l'`id` de la valeur « 2 ». La plaque se construisait donc à
    292 mm d'épaisseur. Le danger était pourtant ANNONCÉ ailleurs : *« les
    options portent leur libellé, jamais leur identifiant »*.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.epaisseur = cls.env["product.attribute"].create({
            "name": "Épaisseur", "custom_type": "float",
            "create_variant": "no_variant",
        })
        cls.deux = cls.env["product.attribute.value"].create(
            {"name": "2", "attribute_id": cls.epaisseur.id})
        cls.teinte = cls.env["product.attribute"].create(
            {"name": "Teinte", "create_variant": "no_variant"})
        cls.chene = cls.env["product.attribute.value"].create(
            {"name": "Chêne", "attribute_id": cls.teinte.id})
        cls.tmpl = cls.env["product.template"].create({
            "name": "Plaque", "config_ok": True,
            "attribute_line_ids": [
                Command.create({"attribute_id": cls.epaisseur.id,
                                "value_ids": [Command.set(cls.deux.ids)]}),
                Command.create({"attribute_id": cls.teinte.id,
                                "value_ids": [Command.set(cls.chene.ids)]}),
            ],
        })
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": cls.tmpl.id, "user_id": cls.env.user.id})
        cls.session.value_ids = [(6, 0, (cls.deux | cls.chene).ids)]

    def test_une_question_NUMÉRIQUE_reçoit_le_nom(self):
        """⚠️ Son identifiant serait un nombre valide — et faux."""
        values = self.session._web_values()
        self.assertEqual(values[self.epaisseur.id], "2")
        self.assertNotEqual(values[self.epaisseur.id], self.deux.id)

    def test_une_question_DISCRÈTE_garde_son_identifiant(self):
        """Lui, se retrouve sans ambiguïté : deux attributs peuvent porter le
        même libellé."""
        self.assertEqual(self.session._web_values()[self.teinte.id], self.chene.id)

    def test_la_portée_de_la_PAGE_porte_bien_le_nombre(self):
        """Le chemin complet, celui que la page reçoit — c'est là que le défaut
        se voyait, et nulle part ailleurs."""
        self.env["product.model3d"].create(
            {"name": "Plaque", "product_tmpl_id": self.tmpl.id})
        scope = self.session.web_state()["scope"]
        self.assertEqual(scope[self.epaisseur.scope_key()], 2.0)
        self.assertNotEqual(scope[self.epaisseur.scope_key()], float(self.deux.id))


@tagged("post_install", "-at_install")
class TestTheWaitingPhoto(HttpCase):
    """La photo d'attente, pour un visiteur qui n'a AUCUN droit — 2026-09-07.

    ⚠️ `/web/image` vérifie la lecture de l'enregistrement : un produit
    configurable n'étant pas forcément publié, l'attente montrait le pictogramme
    d'Odoo — un appareil photo barré à la place de la pièce qu'on vient voir.
    C'est le même mur que les vignettes de valeurs (D-258), franchi de la même
    façon : une route à nous, en `sudo`, autorisée par le JETON.
    """

    #: Un vrai PNG de 1×1 — `fields.Image` refuse ce qui n'en est pas un.
    PNG = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE"
           "hQGAhKmMIQAAAABJRU5ErkJggg==")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmpl = cls.env["product.template"].create({
            "name": "Plaque non publiée",
            "config_ok": True,
            "image_1920": cls.PNG,
        })
        cls.session = cls.env["product.config.session"].create({
            "product_tmpl_id": cls.tmpl.id, "user_id": cls.env.user.id})
        cls.session._ensure_access_token()

    def test_l_état_donne_une_route_À_NOUS_et_non_web_image(self):
        image = self.session.web_state()["image"]
        self.assertTrue(image.endswith("/image"), image)
        self.assertIn(self.session.access_token, image)
        self.assertNotIn("/web/image", image)

    def test_un_visiteur_ANONYME_reçoit_la_photo(self):
        response = self.url_open(self.session.web_state()["image"])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("image/"))
        self.assertTrue(response.content, "une image vide n'est pas une photo")

    def test_un_jeton_INCONNU_n_ouvre_aucune_image(self):
        """⚠️ Le jeton est l'autorisation : une route par identifiant de produit
        aurait ouvert le catalogue entier à qui essaie des numéros (D-190)."""
        response = self.url_open("/configurator/%s/image" % ("x" * 32))
        self.assertEqual(response.status_code, 404)

    def test_un_produit_SANS_photo_ne_promet_rien(self):
        nue = self.env["product.template"].create({"name": "Sans photo",
                                                   "config_ok": True})
        session = self.env["product.config.session"].create({
            "product_tmpl_id": nue.id, "user_id": self.env.user.id})
        session._ensure_access_token()
        self.assertIsNone(session.web_state()["image"])
