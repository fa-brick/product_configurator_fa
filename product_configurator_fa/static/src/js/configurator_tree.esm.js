/**
 * L'ARBRE DU CONFIGURATEUR — la maquette de Gerry (D-210).
 *
 * Trois natures de lignes dans une seule liste : l'ÉTAPE en bandeau, l'ATTRIBUT,
 * et ses VALEURS indentées portant chacune leur condition.
 *
 * ⚠️ **Pourquoi un composant et pas une liste Odoo.** Une liste ne sait ni
 * s'imbriquer ni mêler deux modèles — or l'arbre en tient trois. Le serveur rend
 * donc UNE structure (`get_configurator_tree`), et ce composant l'affiche.
 *
 * ⚠️ **L'étape est un bandeau RENDU, pas un enregistrement de plus.** Le modèle
 * n'a pas changé (D-202) : elle reste un marqueur porté par la ligne qui l'ouvre.
 * C'est ce que la forme (A) promettait — *« le bandeau pourra venir plus tard
 * sans toucher au modèle »*.
 */
import {Component, onWillStart, onWillUpdateProps, useEffect, useRef, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useService} from "@web/core/utils/hooks";
import {useSortable} from "@web/core/utils/sortable_owl";

/**
 * L'ordre des lignes d'attribut après un déplacement.
 *
 * ⚠️ **Seul un ATTRIBUT se déplace.** Un bandeau d'étape n'est pas un
 * enregistrement (D-202) et une valeur appartient à son attribut : les glisser
 * n'aurait rien à écrire. La fonction ne connaît donc que des identifiants de
 * lignes, et rend l'ordre à enregistrer.
 *
 * ⓘ Fonction PURE — c'est la seule part du glisser-déposer qui décide quelque
 * chose, donc la seule qui vaille d'être éprouvée hors du navigateur.
 */
export function reorder(lineIds, fromIndex, toIndex) {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) {
        return [...lineIds];
    }
    const next = [...lineIds];
    const [moved] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    return next;
}

/**
 * Où atterrit la ligne déposée, d'après la ligne restée AU-DESSUS d'elle.
 *
 * ⚠️ Le cœur ne dit pas un index, il dit un VOISIN (`previous`) : c'est la seule
 * chose qu'il sache après avoir promené un fantôme dans le DOM. Le décalage de
 * un vient de ce que la ligne emportée occupe encore sa place dans `ids` —
 * descendre après le voisin n° 3 mène au rang 3, pas 4, si l'on venait d'avant.
 *
 * ⓘ `previousId === null` veut dire « déposé en tête ». Un voisin INCONNU rend
 * −1 : `reorder` traite un index négatif comme un refus, et rien ne bouge.
 *
 * ⓘ Fonction PURE, partagée par les deux ordres — celui des attributs et celui
 * des valeurs.
 */
export function dropIndex(ids, fromIndex, previousId) {
    if (previousId === null) {
        return 0;
    }
    const at = ids.indexOf(previousId);
    if (at < 0) {
        return -1;
    }
    return fromIndex < at ? at : at + 1;
}

/**
 * Met l'arbre à plat, dans l'ordre où il s'affiche.
 *
 * ⚠️ Une valeur ne s'affiche QUE si son attribut est déplié. Rendre toutes les
 * valeurs et les cacher en CSS ferait payer un produit à trois cents valeurs
 * pour rien — et c'est justement le cas que le dialogue existe pour éviter.
 *
 * ⓘ Fonction PURE, exportée : c'est la seule part de ce composant qui décide
 * quelque chose, donc la seule qui vaille d'être éprouvée hors du navigateur.
 */
export function flattenTree(rows, expanded) {
    const flat = [];
    for (const row of rows || []) {
        if (row.kind !== "attribute") {
            flat.push({...row, depth: 0});
            continue;
        }
        const isOpen = expanded.has(row.id);
        flat.push({...row, depth: 0, expanded: isOpen, hasValues: (row.values || []).length > 0});
        if (!isOpen) {
            continue;
        }
        for (const value of row.values || []) {
            flat.push({...value, depth: 1});
        }
    }
    return flat;
}

/**
 * L'arbre tel qu'il sera, AVANT que le serveur l'ait confirmé.
 *
 * ⚠️ **SANS ANTICIPATION, LE DÉPÔT CLIGNOTE.** Constaté à l'écran par Gerry :
 * *« quand je relâche, la ligne retourne à son ancienne position puis revient à
 * la nouvelle »*. Le cœur ne déplace RIEN dans le DOM au dépôt
 * (`applyChangeOnDrop` est faux par défaut) : la ligne reprend sa place, et n'en
 * bouge qu'une fois l'aller-retour serveur terminé — enregistrement du
 * formulaire compris. On rend donc le résultat tout de suite, et la relecture
 * qui suit ne fait plus que confirmer.
 *
 * ⓘ **On anticipe dans l'ÉTAT, jamais dans le DOM.** Déplacer un `<tr>` à la
 * main derrière OWL le mettrait en désaccord avec son arbre interne, et le
 * patch suivant réordonnerait à partir d'un ordre qui n'est plus celui de
 * l'écran. C'est aussi pourquoi `applyChangeOnDrop` reste faux.
 *
 * ⓘ Fonction PURE. Le bandeau d'étape SUIT sa ligne : il est déduit du marqueur
 * qu'elle porte (D-202), donc déplacer la ligne déplace l'étape — exactement ce
 * que fait le serveur.
 */
export function reorderRows(rows, lineIds) {
    const bandeaux = new Map();
    const attributs = new Map();
    for (const row of rows || []) {
        if (row.kind === "step") {
            bandeaux.set(row.line_id, row);
        } else if (row.kind === "attribute") {
            attributs.set(row.id, row);
        }
    }
    const suivant = [];
    for (const id of lineIds) {
        if (bandeaux.has(id)) {
            suivant.push(bandeaux.get(id));
        }
        if (attributs.has(id)) {
            suivant.push(attributs.get(id));
        }
    }
    return suivant;
}

/**
 * Le même service pour les VALEURS d'un attribut.
 *
 * ⓘ Fonction PURE. On remplace la ligne d'attribut plutôt que de muter ses
 * valeurs : `flattenTree` recopie déjà les rangées, mais une mutation en place
 * ne dirait rien à OWL, qui compare des références.
 */
export function reorderRowValues(rows, lineId, valueIds) {
    return (rows || []).map((row) => {
        if (row.kind !== "attribute" || row.id !== lineId) {
            return row;
        }
        const parId = new Map((row.values || []).map((valeur) => [valeur.id, valeur]));
        return {
            ...row,
            values: valueIds.map((id) => parId.get(id)).filter(Boolean),
        };
    });
}

/**
 * Le bandeau change de ligne — il s'ouvre désormais SUR celle-ci.
 *
 * ⓘ Fonction PURE. Le bandeau se pose JUSTE AVANT son attribut : c'est toute la
 * forme (A) de D-202 — ce qui suit une étape lui appartient.
 */
export function moveStepRow(rows, stepId, lineId) {
    const bandeau = (rows || []).find(
        (row) => row.kind === "step" && row.id === stepId
    );
    if (!bandeau) {
        return [...(rows || [])];
    }
    const suivant = [];
    for (const row of rows) {
        if (row === bandeau) {
            continue;
        }
        if (row.kind === "attribute" && row.id === lineId) {
            suivant.push({...bandeau, line_id: lineId});
        }
        suivant.push(row);
    }
    return suivant;
}

export class ConfiguratorTree extends Component {
    static template = "product_configurator_fa.ConfiguratorTree";
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        // ⓘ `editingStep` porte l'étape dont le nom est en cours de saisie — une
        // seule à la fois, comme une section fraîche dans un bon de commande.
        this.state = useState({rows: [], expanded: new Set(), editingStep: null});
        this.rootRef = useRef("root");
        this.stepInputRef = useRef("stepInput");
        // ⚠️ Une saisie qui n'a pas le FOCUS n'est pas une saisie : le cœur donne
        // le focus à la section qu'il vient de créer, sans quoi il faudrait
        // cliquer dedans pour la nommer. `useEffect` plutôt qu'`onPatched` : il
        // ne se déclenche que si l'étape en édition a changé.
        useEffect(
            (input) => {
                if (input) {
                    input.focus();
                    input.select();
                }
            },
            () => [this.stepInputRef.el]
        );
        useSortable({
            ref: this.rootRef,
            // ⚠️ Seules les lignes d'ATTRIBUT portent cette classe : un bandeau
            // d'étape n'est pas un enregistrement, et une valeur suit le sien.
            elements: ".o_config_attribute",
            handle: ".o_config_handle",
            cursor: "grabbing",
            // ⚠️ **LE FANTÔME LAISSÉ EN PLACE EST UN `<tr>` MIS EN BLOC.** Le
            // cœur clone la ligne emportée et lui pose `display: block` en
            // style en ligne (`sortable.js`) : dans un tableau, une rangée en
            // bloc quitte la grille des colonnes, et le tableau se retaille
            // sans elle. `d-table-row` est un utilitaire Bootstrap, donc
            // `!important` : c'est ce qui lui reprend la main. Le cœur fait
            // exactement cela pour ses listes (`list_renderer.js`).
            placeholderClasses: ["d-table-row"],
            onDragStart: ({element}) => this.freezeCellWidths(element),
            onDragEnd: ({element}) => this.releaseCellWidths(element),
            onDrop: ({element, previous}) => this.onDrop(element, previous),
        });
        // ⚠️ **DEUX ORDRES, DONC DEUX POIGNÉES.** Les valeurs vivent dans le même
        // `<tbody>` que leurs attributs : aucun élément du DOM ne les regroupe,
        // et l'option `groups` du cœur en réclamerait un. C'est donc la POIGNÉE
        // qui sépare les deux glissers — le cœur ne démarre une séquence que si
        // le clic tombe dans `elements handle` (`draggable_hook_builder.js`).
        // Le refus d'un dépôt hors de son attribut, lui, se joue au dépôt.
        useSortable({
            ref: this.rootRef,
            // ⚠️ **UNE CLASSE DE TRI, DISTINCTE DE CELLE DE STYLE.** C'est elle
            // qu'on retire aux valeurs des AUTRES attributs le temps d'un
            // glisser (`confineValues`) : retirer `o_config_value` aurait
            // emporté avec elle la teinte et l'opacité du second niveau, et fait
            // clignoter la moitié du tableau.
            elements: ".o_config_value_sortable",
            handle: ".o_config_value_handle",
            cursor: "grabbing",
            placeholderClasses: ["d-table-row"],
            onDragStart: ({element}) => this.freezeCellWidths(element),
            onDragEnd: ({element}) => this.releaseCellWidths(element),
            onDrop: ({element, previous}) => this.onDropValue(element, previous),
        });
        // ⚠️ **UN BANDEAU SE DÉPLACE PAR SON `next`, PAS PAR SON `previous`.**
        // L'étape s'ouvre SUR la ligne qui la suit (D-202) : c'est donc le
        // premier attribut SOUS le point de dépôt qui reçoit le marqueur, pas
        // celui du dessus.
        useSortable({
            ref: this.rootRef,
            elements: ".o_config_step",
            handle: ".o_config_step_handle",
            cursor: "grabbing",
            placeholderClasses: ["d-table-row"],
            onDragStart: ({element}) => this.freezeCellWidths(element),
            onDragEnd: ({element}) => this.releaseCellWidths(element),
            onDrop: ({element, next}) => this.onDropStep(element, next),
        });
        onWillStart(() => this.load());
        // ⚠️ L'arbre est lu du SERVEUR, pas du cache du formulaire : il joint
        // trois modèles. Il doit donc se relire quand l'enregistrement change,
        // sans quoi il montrerait l'état d'avant la dernière sauvegarde.
        onWillUpdateProps(() => this.load());
    }

    get templateId() {
        return this.props.record.resId;
    }

    async load() {
        // ⚠️ **PENDANT UNE ÉCRITURE, NE RIEN RELIRE.** `record.save()` fait
        // repasser le formulaire, donc `onWillUpdateProps`, donc un `load` — qui
        // rendrait l'ordre d'AVANT et effacerait l'anticipation du dépôt. C'est
        // le clignotement, revenu par une autre porte.
        if (this.writing) {
            return;
        }
        if (!this.templateId) {
            this.state.rows = [];
            return;
        }
        this.state.rows = await this.orm.call(
            "product.template", "get_configurator_tree", [[this.templateId]]
        );
    }

    /**
     * Écrire côté SERVEUR, puis remettre le FORMULAIRE d'accord avec lui.
     *
     * ⚠️ **L'ARBRE ÉCRIT EN BASE, LE FORMULAIRE LIT SON CACHE — et les deux
     * divergeaient.** Constat de Gerry : *« l'ordre des attributs doit être
     * identique entre l'onglet attribut et l'onglet configurator »*. Déplacer un
     * attribut ici écrivait la séquence en base sans que le formulaire en sache
     * rien : « Attributs & Variantes » gardait l'ordre d'avant jusqu'au prochain
     * rechargement de la fiche. Et dans l'autre sens, déplacer là-bas ne
     * touchait que le cache : l'arbre, qui relit le SERVEUR, montrait l'ordre
     * d'avant.
     *
     * ⚠️ **SAUVER D'ABORD, ET PAS SEULEMENT RECHARGER.** Recharger jetterait les
     * modifications en cours du formulaire — y compris un déplacement fait dans
     * l'autre onglet et pas encore enregistré. Un `save()` qui échoue (champ
     * requis vide, contrainte) rend `false` : on renonce alors à écrire, plutôt
     * que d'agir sur un état que l'utilisateur n'a pas pu valider.
     */
    async writeAndReload(model, method, args, anticipe) {
        const record = this.props.record;
        // ⚠️ L'arbre ANTICIPÉ est rendu tout de suite : sans lui, la ligne
        // reprend sa place le temps de l'aller-retour, et le dépôt clignote.
        if (anticipe) {
            this.state.rows = anticipe;
        }
        this.writing = true;
        try {
            if ((await record.save()) !== false) {
                await this.orm.call(model, method, args);
                // ⓘ `load` du RECORD : il rafraîchit `attribute_line_ids` pour
                // l'onglet voisin, qui lit ce champ et non notre structure.
                await record.load();
            }
        } finally {
            this.writing = false;
        }
        // ⓘ On relit dans TOUS les cas : après une écriture pour confirmer,
        // après un enregistrement refusé pour DÉFAIRE l'anticipation.
        await this.load();
    }

    get rows() {
        return flattenTree(this.state.rows, this.state.expanded);
    }

    toggle(row) {
        if (this.state.expanded.has(row.id)) {
            this.state.expanded.delete(row.id);
        } else {
            this.state.expanded.add(row.id);
        }
        // `Set` n'est pas réactif par mutation : on le remplace pour que OWL voie.
        this.state.expanded = new Set(this.state.expanded);
    }

    /** Les identifiants de lignes d'attribut, dans l'ordre affiché. */
    get lineIds() {
        return (this.state.rows || [])
            .filter((row) => row.kind === "attribute")
            .map((row) => row.id);
    }

    /**
     * Fige les COLONNES du tableau, le temps d'un glisser.
     *
     * ⚠️ **LE TABLEAU SE REDESSINE DÈS QU'ON LUI RETIRE UNE RANGÉE.** Il est en
     * `table-layout: auto` : ses colonnes se mesurent sur leur contenu, et la
     * rangée emportée — passée en `position: fixed` — n'en fait plus partie. Ce
     * sont donc TOUTES les lignes restantes qui glissent latéralement, pas
     * seulement celle qu'on tire. C'est ce que Gerry a vu sur le JeNo 5".
     *
     * ⚠️ **AU POINTERDOWN, ET PAS PLUS TARD.** Le cœur pose `position: fixed`
     * AVANT d'appeler `onDragStart` (`draggable_hook_builder.js`) : mesurer
     * là-bas, ce serait déjà mesurer le tableau d'après.
     */
    /**
     * Ce qu'il faut préparer AVANT qu'un glisser ne démarre.
     *
     * ⓘ Au `pointerdown`, donc : le cœur a déjà tout mis en place quand il
     * appelle `onDragStart` — la rangée est fixée, et les écouteurs des voisins
     * sont posés. Trop tard pour l'un comme pour l'autre.
     */
    onHandlePointerDown(row) {
        this.freezeColumns();
        if (row.kind === "value") {
            this.confineValues(row.line_id);
        }
    }

    /**
     * Une valeur ne sort pas du bloc de son attribut — même en glissant.
     *
     * ⚠️ **LE REFUS AU DÉPÔT NE SUFFISAIT PAS.** Il empêchait bien l'écriture,
     * mais l'écart s'ouvrait quand même sous les valeurs d'un autre attribut :
     * l'écran promettait un déplacement qui ne se ferait jamais. Demande de
     * Gerry — *« empêcher le drag au-delà de leur zone enfants »*.
     *
     * ⚠️ **ET `groups` NE POUVAIT PAS SERVIR.** L'option du cœur veut un élément
     * PARENT par groupe ; nos valeurs sont toutes sœurs dans un seul `<tbody>`,
     * et un tableau n'admet pas d'autre conteneur de rangées. On retire donc la
     * classe de tri aux étrangères : le cœur ne pose ses écouteurs de survol que
     * sur ce qui répond à `elements` (`sortable.js`, `onDragStart`), et l'écart
     * ne s'ouvre plus que dans le bloc d'origine.
     *
     * ⓘ Une classe qu'OWL réécrirait au prochain rendu — mais aucun rendu n'a
     * lieu pendant un glisser, et la remise en place précède le suivant. Et si
     * un rendu survenait quand même, il RÉTABLIRAIT la bonne valeur : la panne
     * serait un élargissement, pas une corruption.
     */
    confineValues(lineId) {
        const etrangeres = this.rootRef.el.querySelectorAll(
            `.o_config_value_sortable:not([data-line-id="${lineId}"])`
        );
        for (const rangee of etrangeres) {
            rangee.classList.remove("o_config_value_sortable");
            rangee.classList.add("o_config_value_confined");
        }
        // ⚠️ Un simple CLIC ne démarre aucun glisser : `onDragEnd` ne viendrait
        // jamais, et la moitié des valeurs resteraient inertes.
        window.addEventListener("pointerup", () => this.releaseValues(), {once: true});
    }

    /** Les valeurs des autres attributs redeviennent déplaçables. */
    releaseValues() {
        if (!this.rootRef.el) {
            return;
        }
        for (const rangee of this.rootRef.el.querySelectorAll(".o_config_value_confined")) {
            rangee.classList.add("o_config_value_sortable");
            rangee.classList.remove("o_config_value_confined");
        }
    }

    freezeColumns() {
        const table = this.rootRef.el;
        if (!table || table.dataset.frozenColumns) {
            return;
        }
        for (const entete of table.querySelectorAll("thead th")) {
            entete.style.width = `${entete.getBoundingClientRect().width}px`;
        }
        table.style.tableLayout = "fixed";
        table.dataset.frozenColumns = "1";
        // ⚠️ Un simple CLIC sur la poignée ne démarre aucun glisser : `onDragEnd`
        // ne viendrait jamais, et le tableau resterait figé sur des largeurs
        // périmées dès le prochain redimensionnement de la fenêtre.
        window.addEventListener("pointerup", () => this.releaseColumns(), {once: true});
    }

    /** Rend le tableau à sa mise en page souple. */
    releaseColumns() {
        const table = this.rootRef.el;
        if (!table) {
            return;
        }
        for (const entete of table.querySelectorAll("thead th")) {
            entete.style.width = "";
        }
        table.style.tableLayout = "";
        delete table.dataset.frozenColumns;
    }

    /**
     * Fige la largeur des cellules de la ligne qu'on emporte.
     *
     * ⚠️ **UNE RANGÉE TIRÉE QUITTE SON TABLEAU.** Le cœur lui pose
     * `position: fixed` : ses cellules n'ont plus de colonnes auxquelles
     * s'aligner et se retaillent sur leur contenu. Le texte de la ligne tirée
     * glisserait alors, même une fois les colonnes du tableau figées.
     *
     * ⓘ La mesure vient de l'EN-TÊTE, pas de la cellule : c'est l'en-tête qui
     * porte la largeur de colonne — et il est FIGÉ depuis `freezeColumns`, donc
     * il dit encore la largeur d'avant le glisser. Même remède que le cœur pour
     * ses listes (`list_renderer.js`, `sortStart`).
     */
    freezeCellWidths(element) {
        const entetes = [...this.rootRef.el.querySelectorAll("thead th")];
        let colonne = 0;
        for (const cellule of element.querySelectorAll("td")) {
            let largeur = 0;
            // ⓘ Une cellule peut couvrir plusieurs colonnes : on additionne.
            for (let i = 0; i < cellule.colSpan; i++) {
                const entete = entetes[colonne + i];
                if (entete) {
                    largeur += parseFloat(getComputedStyle(entete).width);
                }
            }
            cellule.style.width = `${largeur}px`;
            colonne += cellule.colSpan;
        }
    }

    /**
     * Rend les cellules à la mise en page du tableau.
     *
     * ⚠️ Sur `onDragEnd`, pas sur `onDrop` : un déplacement ABANDONNÉ ne passe
     * pas par `onDrop`, et la ligne resterait figée sur des largeurs qui ne
     * valent plus rien dès que la fenêtre change.
     */
    releaseCellWidths(element) {
        for (const cellule of element.querySelectorAll("td")) {
            cellule.style.width = null;
        }
        this.releaseColumns();
        this.releaseValues();
    }

    /** Les identifiants des valeurs d'un attribut, dans l'ordre affiché. */
    valueIds(lineId) {
        const ligne = (this.state.rows || []).find(
            (row) => row.kind === "attribute" && row.id === lineId
        );
        return ((ligne && ligne.values) || []).map((valeur) => valeur.id);
    }

    /**
     * La ligne d'attribut au-dessus du point de dépôt.
     *
     * ⚠️ **LE VOISIN N'EST PAS FORCÉMENT UN ATTRIBUT.** Il peut être une VALEUR,
     * qui porte l'identifiant de son attribut : déposer sous la dernière valeur
     * de X, c'est bien déposer sous X. On remonte donc jusqu'à la première ligne
     * qui dise quelque chose.
     *
     * ⚠️ **ET LE BANDEAU D'ÉTAPE SE SAUTE.** Il porte lui aussi un
     * `data-line-id` depuis qu'il se déplace — mais celui de la ligne qu'il
     * OUVRE, c'est-à-dire celle qui le suit. S'y arrêter renverrait une ligne
     * située EN DESSOUS du point de dépôt : l'attribut déposé sous un bandeau
     * aurait sauté d'un cran de trop.
     *
     * ⓘ `null` veut dire « rien au-dessus » : dépôt en tête.
     */
    previousLineId(node) {
        let curseur = node;
        while (curseur && (this.isStepRow(curseur) || !curseur.dataset.lineId)) {
            curseur = curseur.previousElementSibling;
        }
        return curseur ? Number(curseur.dataset.lineId) : null;
    }

    /** ⓘ Un bandeau d'étape : il porte un `data-line-id` qui n'est pas le sien. */
    isStepRow(node) {
        return node.classList.contains("o_config_step");
    }

    /**
     * La valeur au-dessus du point de dépôt — DANS le même attribut.
     *
     * ⚠️ **UNE VALEUR NE CHANGE PAS D'ATTRIBUT EN GLISSANT.** Rien dans le DOM
     * ne l'en empêche : toutes les lignes partagent un `<tbody>`, et l'option
     * `groups` du cœur réclamerait un élément parent par groupe. Le refus se
     * joue donc ici — `-1`, que `dropIndex` puis `reorder` traitent comme un
     * non-mouvement.
     *
     * ⓘ `null` quand le voisin est la ligne d'ATTRIBUT elle-même : la valeur
     * passe en tête de son bloc.
     */
    previousValueId(node, lineId) {
        if (!node || this.isStepRow(node) || Number(node.dataset.lineId) !== lineId) {
            return -1;
        }
        return node.dataset.valueId ? Number(node.dataset.valueId) : null;
    }

    async onDrop(element, previous) {
        const moved = Number(element.dataset.lineId);
        const ids = this.lineIds;
        const from = ids.indexOf(moved);
        const ordonne = reorder(ids, from, dropIndex(ids, from, this.previousLineId(previous)));
        await this.writeAndReload(
            "product.template", "configurator_reorder", [[this.templateId], ordonne],
            reorderRows(this.state.rows, ordonne)
        );
    }

    /**
     * ⚠️ **CET ORDRE APPARTIENT À L'ATTRIBUT, PAS AU PRODUIT** — arbitré par
     * Gerry le 2026-08-29. Une valeur est un `product.attribute.value` et son
     * rang vit dans sa `sequence` : la déplacer ici la déplace sur tous les
     * produits qui emploient cet attribut. C'est le seul ordre qui existe — en
     * inventer un par produit obligerait tout ce qui affiche des valeurs à le
     * relire.
     */
    async onDropValue(element, previous) {
        const lineId = Number(element.dataset.lineId);
        const moved = Number(element.dataset.valueId);
        const ids = this.valueIds(lineId);
        const from = ids.indexOf(moved);
        const to = dropIndex(ids, from, this.previousValueId(previous, lineId));
        if (to < 0) {
            // Dépôt hors de son attribut : le cœur n'a rien touché au DOM
            // (`applyChangeOnDrop` est faux), la ligne est déjà revenue seule.
            return;
        }
        const ordonne = reorder(ids, from, to);
        await this.writeAndReload(
            "product.template", "configurator_reorder_values",
            [[this.templateId], lineId, ordonne],
            reorderRowValues(this.state.rows, lineId, ordonne)
        );
    }

    async removeFacet(row, facet) {
        await this.writeAndReload(
            "product.template", "configurator_remove_facet", [[this.templateId], facet.id]
        );
    }

    async removeRow(row) {
        if (row.kind === "step") {
            await this.writeAndReload(
                "product.template", "configurator_clear_step",
                [[this.templateId], row.line_id]
            );
        } else if (row.kind === "value") {
            await this.writeAndReload(
                "product.template", "configurator_remove_value",
                [[this.templateId], row.line_id, row.id]
            );
        } else {
            await this.writeAndReload(
                "product.template.attribute.line", "unlink", [[row.id]]
            );
        }
    }

    /**
     * ⚠️ L'ARBRE VIDE DOIT DIRE QUOI FAIRE. Une liste sans ligne et sans point
     * d'entrée n'est pas « vide » : elle est cassée, du point de vue de qui la
     * regarde. Constaté à l'écran par Gerry sur un produit sans attribut.
     */
    get isEmpty() {
        return !(this.state.rows || []).length;
    }

    /**
     * Pose une étape — le geste d'« Ajouter une section », pas un dialogue.
     *
     * ⚠️ **UNE ÉTAPE NE SE POSE PAS « EN BAS ».** C'est un marqueur porté par la
     * ligne qui l'ouvre (D-202) : il n'y a aucune ligne sous la dernière. Le
     * serveur la pose donc sur la dernière ligne LIBRE — au plus bas qu'un
     * marqueur puisse aller — et le glisser fait le reste.
     *
     * ⓘ Elle s'ouvre en SAISIE : comme une section fraîche, elle attend son nom.
     */
    async addStep() {
        const record = this.props.record;
        let stepId = null;
        this.writing = true;
        try {
            if ((await record.save()) !== false) {
                stepId = await this.orm.call(
                    "product.template", "configurator_add_step", [[this.templateId]]
                );
                await record.load();
            }
        } finally {
            this.writing = false;
        }
        await this.load();
        // ⓘ Après la relecture : le bandeau doit EXISTER pour que sa saisie
        // s'ouvre — l'ouvrir avant nommerait une rangée que rien ne rend encore.
        this.state.editingStep = stepId;
    }

    /** Le nom du bandeau devient une saisie. */
    editStep(row) {
        this.state.editingStep = row.id;
    }

    /**
     * Enregistre le nom saisi — et referme la saisie.
     *
     * ⚠️ **CE NOM EST CELUI D'UN ENREGISTREMENT PARTAGÉ.** `product.config.step`
     * est une fiche de catalogue : renommer une étape qu'un autre produit
     * emploie le renomme là-bas aussi. En pratique le cas est rare — « Ajouter
     * une étape » en crée une NEUVE à chaque fois, donc celle qu'on nomme vient
     * d'être créée pour ce produit-ci.
     *
     * ⓘ Un nom inchangé n'écrit rien : le `blur` qui suit une touche Entrée
     * repasserait ici, et deux écritures pour une frappe.
     */
    async commitStepName(row, name) {
        this.state.editingStep = null;
        const nom = (name || "").trim();
        if (!nom || nom === row.name) {
            return;
        }
        await this.writeAndReload(
            "product.template", "configurator_rename_step",
            [[this.templateId], row.id, nom]
        );
    }

    /**
     * ⓘ Entrée valide, Échap renonce — les deux touches que le cœur donne à
     * toute saisie en ligne. `blur` fait le reste : cliquer ailleurs valide.
     */
    onStepKeydown(ev, row) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.target.blur();
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            // ⚠️ On referme AVANT de rendre la main : sans cela le `blur` qui
            // suit enregistrerait la valeur qu'on vient de refuser.
            ev.target.value = row.name;
            ev.target.blur();
        }
    }

    /**
     * La première ligne d'ATTRIBUT sous le point de dépôt.
     *
     * ⚠️ **UN BANDEAU S'OUVRE SUR CE QUI LE SUIT**, pas sur ce qui le précède —
     * c'est toute la forme (A) de D-202. On regarde donc vers le bas, et on ne
     * s'arrête que sur un attribut : une VALEUR porte l'identifiant de sa ligne,
     * qui est AU-DESSUS d'elle, et poser le marqueur là ferait remonter le
     * bandeau par-dessus les valeurs qu'on venait de dépasser.
     *
     * ⓘ `null` : rien en dessous — une étape qui n'ouvre rien n'existe pas.
     */
    nextAttributeLineId(node) {
        let curseur = node;
        while (curseur && !curseur.classList.contains("o_config_attribute")) {
            curseur = curseur.nextElementSibling;
        }
        return curseur ? Number(curseur.dataset.lineId) : null;
    }

    async onDropStep(element, next) {
        const stepId = Number(element.dataset.stepId);
        const lineId = this.nextAttributeLineId(next);
        if (!lineId) {
            // Déposé sous la dernière ligne : il n'y a rien à ouvrir. Le cœur
            // n'a pas touché au DOM (`applyChangeOnDrop` est faux), le bandeau
            // est déjà revenu seul.
            return;
        }
        await this.writeAndReload(
            "product.template", "configurator_move_step",
            [[this.templateId], stepId, lineId],
            moveStepRow(this.state.rows, stepId, lineId)
        );
    }

    /**
     * ⚠️ La cellule « Conditions » s'ouvre même VIDE : c'est par elle qu'on en
     * pose une. Sans cela, retirer « Configuration Restrictions » aurait retiré
     * le seul endroit d'où l'on crée une condition par valeur.
     */
    async openCondition(row) {
        const action = await this.orm.call(
            "product.template", "configurator_open_condition",
            [[this.templateId], row.kind === "value" ? row.line_id : row.id,
             row.kind === "value" ? row.id : false]
        );
        this.action.doAction(action, {onClose: () => this.load()});
    }

    async openStep(row) {
        const action = await this.orm.call(
            "product.template", "configurator_open_step", [[this.templateId], row.line_id]
        );
        if (action) {
            this.action.doAction(action, {onClose: () => this.load()});
        }
    }

    /**
     * ⚠️ Les réglages d'une ligne — mode de prix, bornes, rôle de dimension, vue
     * 3D — n'étaient joignables NULLE PART depuis la fiche produit : le bouton
     * « Configurer » du cœur ouvre les valeurs, pas la ligne. Le nom de
     * l'attribut devient donc la porte de ses réglages.
     */
    async openLine(row) {
        const action = await this.orm.call(
            "product.template.attribute.line", "action_open_configurator_line",
            [[row.id]]
        );
        this.action.doAction(action, {onClose: () => this.load()});
    }

    async openValues(row) {
        const action = await this.orm.call(
            "product.template.attribute.line", "action_open_values", [[row.id]]
        );
        this.action.doAction(action, {onClose: () => this.load()});
    }
}

export const configuratorTreeField = {
    component: ConfiguratorTree,
    supportedTypes: ["one2many"],
};

registry.category("fields").add("configurator_tree", configuratorTreeField);
