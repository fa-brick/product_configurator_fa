#!/usr/bin/env python3
"""Vérifie que tout identifiant XML référencé sous le préfixe des modules forkés
existe bien. Un renommage partiel ne casse PAS au chargement : il casse plus tard,
à l'exécution, quand env.ref() ne trouve rien. Ce contrôle rend la panne immédiate.
"""
import csv
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = sys.argv[1]
MODULES = [d for d in os.listdir(ROOT) if d.startswith("product_configurator_fa")]
PREFIX = "product_configurator_fa"

defined = set()  # "module.id"
referenced = []  # (identifiant, module, fichier, ligne)


def walk(module):
    base = os.path.join(ROOT, module)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            yield os.path.join(dirpath, fn)


# --- identifiants DÉFINIS -------------------------------------------------
for module in MODULES:
    for path in walk(module):
        if path.endswith(".xml"):
            try:
                tree = ET.parse(path)
            except ET.ParseError:
                continue
            for el in tree.iter():
                rid = el.get("id")
                if rid and el.tag in ("record", "template", "menuitem", "act_window", "report"):
                    defined.add(rid if "." in rid else f"{module}.{rid}")
        elif path.endswith("ir.model.access.csv"):
            with open(path, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    rid = row.get("id")
                    if rid:
                        defined.add(rid if "." in rid else f"{module}.{rid}")

# les modèles produisent un identifiant implicite model_<nom_du_modèle>
for module in MODULES:
    for path in walk(module):
        if path.endswith(".py"):
            src = open(path, encoding="utf-8").read()
            for m in re.finditer(r'_name\s*=\s*["\']([\w.]+)["\']', src):
                defined.add(f"{module}.model_" + m.group(1).replace(".", "_"))

# --- identifiants RÉFÉRENCÉS ---------------------------------------------
PATTERNS = [
    re.compile(r'\bref\(\s*["\']([\w.]*' + PREFIX + r'[\w.]*)["\']'),
    re.compile(r'\bgroups\s*=\s*["\']([^"\']*)["\']'),
    re.compile(r'%\(\s*(' + PREFIX + r'[\w.]+)\s*\)'),
]
for module in MODULES:
    for path in walk(module):
        if not path.endswith((".py", ".xml", ".csv")):
            continue
        for lineno, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
            for pat in PATTERNS:
                for m in pat.finditer(line):
                    for token in m.group(1).split(","):
                        token = token.strip().lstrip("!")
                        # « contient », et non « commence par » : un identifiant
                        # implicite de modèle porte le nom du module APRÈS son
                        # préfixe `model_`. Le filtrer sur le début le rendait
                        # invisible — c'est ce qui a laissé passer
                        # `model_product_configurator_fa` (L-110).
                        if PREFIX in token:
                            referenced.append((token, module, path, lineno))
        # colonnes *:id du CSV d'accès
        if path.endswith("ir.model.access.csv"):
            with open(path, newline="", encoding="utf-8") as fh:
                for i, row in enumerate(csv.DictReader(fh), 2):
                    for col, val in row.items():
                        if col.endswith(":id") and val and PREFIX in val:
                            referenced.append((val, module, path, i))

def resolves(token, module):
    """Un identifiant nu (`group_x`, `model_y`) vaut `<module_citant>.<identifiant>`."""
    return token in defined or f"{module}.{token}" in defined


missing = [(r, f, l) for (r, m, f, l) in referenced if not resolves(r, m)]

# --- templates QWeb réclamés par le JS -----------------------------------
# Même mode de panne que les identifiants XML, mais côté OWL : la définition
# t-name et la référence `static template =` sont dans deux fichiers distincts,
# donc un renommage peut n'en toucher qu'un. Rien ne le dit avant l'exécution.
qweb_defined, qweb_referenced = set(), []
for module in MODULES:
    for path in walk(module):
        if path.endswith(".xml"):
            for lineno, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
                for m in re.finditer(r't-name=["\']([\w.]+)["\']', line):
                    qweb_defined.add(m.group(1))
        elif path.endswith(".js"):
            for lineno, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
                for m in re.finditer(r'\btemplate\s*=\s*["\']([\w.]+\.[\w.]+)["\']', line):
                    qweb_referenced.append((m.group(1), path, lineno))
qweb_missing = [(t, f, l) for (t, f, l) in qweb_referenced if t not in qweb_defined]

# --- survivances de l'ANCIEN nom -----------------------------------------
# Sans ce contrôle, une référence oubliée à l'ancien module est INVISIBLE :
# elle ne porte pas le nouveau préfixe, donc rien ne la collecte, et le
# compteur de références baisse en silence au lieu de signaler une erreur.
OLD = re.compile(r"\bproduct_configurator(?!_fa)(_sale|_mrp)?\b")
survivances = []
for module in MODULES:
    for path in walk(module):
        if not path.endswith((".py", ".xml", ".csv", ".po", ".pot", ".js")):
            continue
        for lineno, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
            if OLD.search(line):
                survivances.append((path, lineno, line.strip()[:90]))

print(f"identifiants définis   : {len(defined)}")
print(f"références au préfixe  : {len(referenced)}")
print(f"références IRRÉSOLUES  : {len(missing)}")
print(f"survivances ancien nom : {len(survivances)}")
print(f"templates QWeb définis : {len(qweb_defined)}  réclamés : {len(qweb_referenced)}"
      f"  INTROUVABLES : {len(qweb_missing)}")
for r, f, l in sorted(set(missing)):
    print(f"  ⚠ irrésolu {r}\n      {os.path.relpath(f, ROOT)}:{l}")
for f, l, txt in survivances[:20]:
    print(f"  ⚠ ancien nom {os.path.relpath(f, ROOT)}:{l}\n      {txt}")
for t, f, l in qweb_missing:
    print(f"  ⚠ template QWeb introuvable {t}\n      {os.path.relpath(f, ROOT)}:{l}")
sys.exit(1 if (missing or survivances or qweb_missing) else 0)
