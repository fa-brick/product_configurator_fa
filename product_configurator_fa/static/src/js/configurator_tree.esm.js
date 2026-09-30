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
 * L'arbre découpé en BLOCS — un par attribut.
 *
 * ⚠️ **LE FANTÔME D'UNE VALEUR DOIT ÊTRE BORNÉ, ET SEUL UN CONTENEUR BORNE.**
 * Demande de Gerry : *« borner le fantôme pour qu'il représente l'emplacement du
 * relâcher »*. Le cœur sait le faire — `groups` + `connectGroups: false` fait de
 * l'élément de groupe le CONTENEUR de la rangée tirée, et `updateElementPosition`
 * l'y enferme (`draggable_hook_builder.js`). Mais il lui faut un élément PARENT
 * par groupe, et un tableau n'admet qu'un seul genre de conteneur de rangées :
 * le `<tbody>`. D'où ce découpage — la tête du bloc (bandeau d'étape éventuel et
 * rangée d'attribut) dans un `<tbody>`, ses valeurs dans un autre.
 *
 * ⓘ Le bandeau précède TOUJOURS l'attribut qu'il ouvre (D-202) : ils font une
 * seule tête. Fonction PURE.
 */
export function groupRows(flat) {
    const blocs = [];
    for (const row of flat || []) {
        const dernier = blocs[blocs.length - 1];
        if (row.kind === "value") {
            if (dernier) {
                dernier.values.push(row);
            }
            continue;
        }
        if (
            row.kind === "attribute" &&
            dernier &&
            dernier.openedByStep &&
            dernier.head.length === 1 &&
            dernier.lineId === row.id
        ) {
            dernier.head.push(row);
            continue;
        }
        blocs.push({
            lineId: row.kind === "step" ? row.line_id : row.id,
            head: [row],
            values: [],
            openedByStep: row.kind === "step",
        });
    }
    return blocs;
}

/**
 * L'arbre après le dépôt d'un ATTRIBUT : l'ordre des lignes, et la ligne que
 * chaque bandeau ouvre désormais.
 *
 * ⚠️ **UN BANDEAU RESTE OÙ IL S'AFFICHE ; SEUL L'ATTRIBUT BOUGE.** Constat de
 * Gerry sur le JeNo 5" : *« je n'arrive pas à déplacer Bottom Plate au-dessus
 * de Impressions 3D »*. Bottom Plate PORTAIT le marqueur de l'étape (D-202) :
 * le bandeau, déduit de lui, le suivait partout. Déposé juste au-dessus de son
 * propre bandeau, l'attribut ne changeait pas de rang, et rien ne bougeait —
 * le fantôme montrait un dépôt que le résultat démentait. L'inverse aussi :
 * glisser l'attribut suivant ENTRE le bandeau et Bottom Plate le rendait
 * au-dessus du bandeau, hors de l'étape où le fantôme l'avait posé.
 *
 * On lit donc l'écran tel que le fantôme le montre : chaque bandeau s'ouvre sur
 * le premier attribut qui le suit. Le marqueur passe d'une ligne à l'autre ; il
 * ne s'emporte plus.
 *
 * ⓘ **Une étape qu'on viderait garde l'ancien comportement** — le bandeau suit
 * sa ligne (`steps: null`). Une étape qui n'ouvre rien n'existe pas, et quand
 * elle ne tient qu'une ligne, déplacer cette ligne, c'est déplacer l'étape.
 *
 * ⓘ Fonction PURE, sur des descripteurs `{kind, lineId, stepId, transient}` ;
 * `at` est l'index de la rangée juste au-dessus du point de dépôt (−1 : en
 * tête). Rend `{order, steps}`, `steps` étant des paires `[stepId, lineId]`.
 */
export function dropLayout(rows, at, movedLineId) {
    const keep = (row) =>
        !row.transient &&
        (row.kind === "step" ||
            (row.kind === "attribute" && row.lineId !== movedLineId));
    return layoutOf([
        ...rows.slice(0, at + 1).filter(keep),
        {kind: "attribute", lineId: movedLineId},
        ...rows.slice(at + 1).filter(keep),
    ]);
}

/**
 * L'arbre après le dépôt d'un BANDEAU — la même lecture que pour un attribut.
 *
 * ⚠️ **LE BANDEAU SE POSE OÙ LE FANTÔME L'A MONTRÉ, ET CHAQUE BANDEAU S'OUVRE SUR
 * LE PREMIER ATTRIBUT QUI LE SUIT.** Constat de Gerry : *« je ne peux pas déplacer
 * ma nouvelle étape créée au début de la liste »*. L'ancien calcul ne regardait
 * que la ligne sous le point de dépôt : déposé contre un autre bandeau, il visait
 * une ligne qui ouvrait DÉJÀ une étape, et le serveur refusait. Lu ainsi, poser
 * « New Step » en tête l'ouvre sur la première ligne, et la ligne qu'il ouvrait
 * rejoint l'étape d'au-dessus.
 *
 * ⓘ `null` : une étape en sortirait VIDE — déposée sous la dernière ligne, ou
 * collée contre un autre bandeau. Une étape qui n'ouvre rien n'existe pas : on
 * ne dépose pas.
 *
 * ⓘ Fonction PURE, mêmes descripteurs que `dropLayout`.
 */
export function stepDropLayout(rows, at, movedStepId) {
    const keep = (row) =>
        !row.transient &&
        (row.kind === "attribute" ||
            (row.kind === "step" && row.stepId !== movedStepId));
    const layout = layoutOf([
        ...rows.slice(0, at + 1).filter(keep),
        {kind: "step", stepId: movedStepId},
        ...rows.slice(at + 1).filter(keep),
    ]);
    return layout.steps ? layout : null;
}

/**
 * Ce qu'une suite de rangées dit : l'ordre des lignes, et la ligne que chaque
 * bandeau ouvre — `steps: null` si un bandeau n'ouvre rien.
 */
function layoutOf(tokens) {
    const order = tokens
        .filter((token) => token.kind === "attribute")
        .map((token) => token.lineId);
    const steps = [];
    for (let i = 0; i < tokens.length; i++) {
        if (tokens[i].kind !== "step") {
            continue;
        }
        const opened = tokens[i + 1];
        if (!opened || opened.kind !== "attribute") {
            return {order, steps: null};
        }
        steps.push([tokens[i].stepId, opened.lineId]);
    }
    return {order, steps};
}

/**
 * Les bandeaux posés sur leurs nouvelles lignes — l'anticipation de `dropLayout`.
 *
 * ⓘ Fonction PURE. À composer avec `reorderRows`, qui range chaque bandeau
 * devant la ligne dont il porte l'identifiant.
 */
export function restepRows(rows, steps) {
    const lineOf = new Map(steps || []);
    return (rows || []).map((row) =>
        row.kind === "step" && lineOf.has(row.id)
            ? {...row, line_id: lineOf.get(row.id)}
            : row
    );
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

export class ConfiguratorTree extends Component {
    static template = "product_configurator_fa.ConfiguratorTree";
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        // ⓘ `editingStep` porte l'étape dont le nom est en cours de saisie — une
        // seule à la fois, comme une section fraîche dans un bon de commande.
        // ⓘ `cameras` : les vues 3D du produit, la liste déroulante de la colonne « Vue
        // 3D » (D-386) — vide sans le pont 3D, et la colonne montre alors un nom.
        this.state = useState({rows: [], expanded: new Set(), editingStep: null, cameras: []});
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
            placeholderClasses: ["d-table-row", "o_config_ghost"],
            onDragStart: ({element}) => this.freezeCellWidths(element),
            onDragEnd: ({element}) => this.releaseCellWidths(element),
            onDrop: ({element, previous, next}) => this.onDrop(element, previous, next),
        });
        // ⚠️ **DEUX ORDRES, DONC DEUX POIGNÉES.** Les valeurs vivent dans le même
        // `<tbody>` que leurs attributs : aucun élément du DOM ne les regroupe,
        // et l'option `groups` du cœur en réclamerait un. C'est donc la POIGNÉE
        // qui sépare les deux glissers — le cœur ne démarre une séquence que si
        // le clic tombe dans `elements handle` (`draggable_hook_builder.js`).
        // Le refus d'un dépôt hors de son attribut, lui, se joue au dépôt.
        useSortable({
            ref: this.rootRef,
            elements: ".o_config_value",
            handle: ".o_config_value_handle",
            cursor: "grabbing",
            // ⚠️ **C'EST `groups` QUI BORNE LE FANTÔME.** Avec
            // `connectGroups: false`, le cœur fait du groupe le CONTENEUR de la
            // rangée tirée et l'y enferme (`draggable_hook_builder.js`,
            // `updateElementPosition`) : la valeur ne peut plus se promener sous
            // un autre attribut, et son fantôme montre donc toujours où elle
            // retombera. C'est pour cela — et pour cela seul — que l'arbre est
            // découpé en `<tbody>`.
            groups: "tbody.o_config_values",
            connectGroups: false,
            placeholderClasses: ["d-table-row", "o_config_ghost"],
            onDragStart: ({element}) => this.freezeCellWidths(element),
            onDragEnd: ({element}) => this.releaseCellWidths(element),
            onDrop: ({element, previous}) => this.onDropValue(element, previous),
        });
        // ⚠️ **LE FANTÔME D'UN BANDEAU DOIT POUVOIR PASSER ENTRE LES ATTRIBUTS.**
        // Le cœur ne déplace le fantôme qu'au survol des `elements`
        // (`sortable.js`, `onElementPointerEnter`) : limités aux bandeaux, un
        // bandeau seul ne bougeait JAMAIS, et deux ne faisaient qu'échanger leurs
        // places — c'est ce que Gerry a vu. Les attributs sont donc des éléments
        // de ce glisser aussi ; seule la POIGNÉE d'étape le démarre, et un
        // attribut n'en porte pas.
        //
        // ⚠️ **UNE CLASSE, JAMAIS UNE LISTE À VIRGULE** ([[L-473]]). Le cœur
        // colle `elements + " " + handle` (`draggable_hook_builder.js`) :
        // `".o_config_step, .o_config_attribute"` devenait « `.o_config_step`
        // OU `.o_config_attribute .o_config_step_handle` » — tout le bandeau
        // démarrait un glisser, et son `preventDefault` empêchait la liste
        // déroulante de la vue 3D de s'ouvrir (Gerry, 2026-09-30).
        useSortable({
            ref: this.rootRef,
            elements: ".o_config_row",
            handle: ".o_config_step_handle",
            cursor: "grabbing",
            placeholderClasses: ["d-table-row", "o_config_ghost"],
            onDragStart: ({element}) => this.freezeCellWidths(element),
            onDragEnd: ({element}) => this.releaseCellWidths(element),
            onDrop: ({element, previous, next}) => this.onDropStep(element, previous, next),
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
        const [rows, cameras] = await Promise.all([
            this.orm.call("product.template", "get_configurator_tree", [[this.templateId]]),
            this.orm.call("product.template", "configurator_camera_choices", [[this.templateId]]),
        ]);
        this.state.rows = rows;
        this.state.cameras = cameras;
    }

    /**
     * Choisir la vue 3D d'un attribut ou d'une étape — D-386.
     *
     * ⓘ `row.id` désigne la ligne d'attribut, ou l'ÉTAPE (`product.config.step`) pour un
     * bandeau : le serveur retrouve la ligne d'étape du produit. Une valeur vide efface
     * la vue — la caméra ne bouge plus (D-163).
     */
    async setCamera(row, value) {
        await this.writeAndReload(
            "product.template", "configurator_set_camera",
            [[this.templateId], row.kind, row.id, value ? Number(value) : false]
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
            // ⓘ On relit dans TOUS les cas : après une écriture pour confirmer,
            // après un enregistrement refusé pour DÉFAIRE l'anticipation.
            // ⚠️ DANS le `finally` : un refus du serveur LÈVE, et la relecture
            // placée après était sautée — l'arbre gardait l'état anticipé, deux
            // bandeaux empilés que la base n'avait jamais eus (capture de Gerry).
            await this.load();
        }
    }

    get rows() {
        return flattenTree(this.state.rows, this.state.expanded);
    }

    /** L'arbre découpé en blocs — c'est ce que le gabarit parcourt. */
    get blocks() {
        return groupRows(this.rows);
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

    /**
     * Toutes les rangées du corps, décrites pour les calculs de dépôt.
     *
     * ⚠️ **UNE SEULE LISTE, PLUSIEURS `<tbody>`.** Depuis que chaque attribut a
     * son conteneur, `previousElementSibling` s'arrête au bord d'un bloc : une
     * rangée déposée en tête d'un bloc n'aurait plus aucun voisin au-dessus.
     * `querySelectorAll` traverse, lui.
     *
     * ⓘ `transient` : la rangée qu'on emporte et le fantôme laissé en place sont
     * encore dans le DOM au moment du dépôt. Ils ne désignent rien.
     */
    bodyRows() {
        return [...this.rootRef.el.querySelectorAll("tbody > tr")].map((el) => ({
            el,
            kind: el.classList.contains("o_config_step")
                ? "step"
                : el.classList.contains("o_config_attribute")
                ? "attribute"
                : el.classList.contains("o_config_value")
                ? "value"
                : "other",
            lineId: el.dataset.lineId ? Number(el.dataset.lineId) : null,
            stepId: el.dataset.stepId ? Number(el.dataset.stepId) : null,
            transient:
                el.classList.contains("o_dragged") ||
                el.classList.contains("o_config_ghost"),
        }));
    }

    /**
     * L'index du point de dépôt dans la liste plate.
     *
     * ⓘ Le cœur ne nomme que des VOISINS. `previous` d'abord — c'est la rangée
     * juste au-dessus. À défaut, on se repère sur `next` : ce qui le précède est
     * le fantôme, que les fonctions de parcours sauteront. `-1` : ni l'un ni
     * l'autre, donc rien à calculer.
     */
    dropAt(rows, previous, next) {
        if (previous) {
            return rows.findIndex((row) => row.el === previous);
        }
        if (next) {
            return rows.findIndex((row) => row.el === next) - 1;
        }
        return -1;
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
    }

    /** Les identifiants des valeurs d'un attribut, dans l'ordre affiché. */
    valueIds(lineId) {
        const ligne = (this.state.rows || []).find(
            (row) => row.kind === "attribute" && row.id === lineId
        );
        return ((ligne && ligne.values) || []).map((valeur) => valeur.id);
    }

    /**
     * La valeur au-dessus du point de dépôt — DANS le même attribut.
     *
     * ⓘ `null` : rien au-dessus DANS SON BLOC, la valeur passe en tête. C'est le
     * cas ordinaire depuis le découpage en `<tbody>` — la rangée d'attribut vit
     * dans un autre conteneur, elle n'est plus le voisin du dessus.
     *
     * ⚠️ Le contrôle d'appartenance RESTE, bien que `groups` empêche désormais
     * la valeur de sortir de son bloc : c'est la barrière qui ne dépend pas de
     * l'interface (D-080). `-1`, que `dropIndex` puis `reorder` traitent comme
     * un non-mouvement.
     */
    previousValueId(node, lineId) {
        if (!node) {
            return null;
        }
        if (!node.dataset.valueId || Number(node.dataset.lineId) !== lineId) {
            return -1;
        }
        return Number(node.dataset.valueId);
    }

    /**
     * ⚠️ Les bandeaux restent où ils s'affichent — voir `dropLayout`. Le serveur
     * reçoit l'ordre ET les marqueurs dans le même appel : les écrire en deux
     * fois laisserait voir, entre les deux, une étape ouverte sur la mauvaise
     * ligne.
     */
    async onDrop(element, previous, next) {
        const moved = Number(element.dataset.lineId);
        const rangees = this.bodyRows();
        const {order, steps} = dropLayout(
            rangees, this.dropAt(rangees, previous, next), moved
        );
        await this.writeAndReload(
            "product.template", "configurator_reorder",
            [[this.templateId], order, steps],
            reorderRows(restepRows(this.state.rows, steps), order)
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
     * ⓘ Le même appel que le dépôt d'un attribut (`configurator_reorder`) :
     * l'ordre ne change pas, les marqueurs si — et plusieurs à la fois quand le
     * bandeau passe au-dessus d'un autre.
     */
    async onDropStep(element, previous, next) {
        const rangees = this.bodyRows();
        const layout = stepDropLayout(
            rangees, this.dropAt(rangees, previous, next), Number(element.dataset.stepId)
        );
        if (!layout) {
            // Une étape en sortirait vide. Le cœur n'a pas touché au DOM
            // (`applyChangeOnDrop` est faux) : le bandeau est déjà revenu seul.
            return;
        }
        await this.writeAndReload(
            "product.template", "configurator_reorder",
            [[this.templateId], layout.order, layout.steps],
            reorderRows(restepRows(this.state.rows, layout.steps), layout.order)
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
