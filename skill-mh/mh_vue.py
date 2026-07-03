"""Liste les monstres (ou trolls/tresors/champignons/lieux) visibles dans la Vue du troll.

Usage:
    python3 mh_vue.py [categorie] [filtre]

categorie : monstres (defaut) | trolls | tresors | champignons | lieux | cenotaphes
filtre    : sous-chaine (insensible a la casse) a chercher dans le nom, ex "Djinn"

Sortie JSON: liste triee par distance croissante, chaque entree :
    {"id":..., "nom":..., "x":..., "y":..., "n":..., "dist":...}

`dist` est la distance de Chebyshev (max(|dx|,|dy|)) calculee par le jeu et
NE tient PAS compte de la difference de N (noeud/dimension) - deux cases avec
le meme X/Y mais un N different peuvent avoir dist=0 alors qu'elles ne sont
pas sur le meme "plan". Voir mh_move_toward.py pour le cout reel en PA qui
lui prend N en compte.

PIEGE : l'endpoint json_vue.php renvoie la chaine "KO" (pas du JSON) si les
en-tetes HTTP suivants ne sont pas envoyes : X-Requested-With: XMLHttpRequest
et un Referer pointant vers Play_vue2.php.
"""
import json
import re
import sys

from mh_common import get_session

VUE_BASE = "https://mh2.mh.raistlin.fr/mountyhall/MH_PageUtils/Services/json_vue.php"


def get_troll_id(session):
    r = session.get("https://mh2.mh.raistlin.fr/mountyhall/MH_Play/Play_vue2.php")
    m = re.search(r'data-idtroll="(\d+)"', r.text)
    if not m:
        raise RuntimeError("Impossible de trouver l'idtroll sur Play_vue2.php")
    return m.group(1)


def fetch_category(session, idtroll, categorie="monstres"):
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://mh2.mh.raistlin.fr/mountyhall/MH_Play/Play_vue2.php",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    r = session.get(VUE_BASE, params={"w": categorie, "t": idtroll}, headers=headers)
    if r.text.strip() == "KO":
        raise RuntimeError("Le serveur a renvoye KO - session invalide ou en-tetes manquants")
    return r.json()


def parse_entries(raw):
    out = []
    for entry in raw:
        v = entry["value"]
        label = re.sub(r"<[^>]+>", "", v.get("nom", {}).get("value", "")).strip()
        out.append({
            "id": v.get("id"),
            "nom": label,
            "x": v.get("x"),
            "y": v.get("y"),
            "n": v.get("n"),
            "dist": v.get("dist"),
        })
    out.sort(key=lambda e: e["dist"] if e["dist"] is not None else 999999)
    return out


if __name__ == "__main__":
    categorie = sys.argv[1] if len(sys.argv) > 1 else "monstres"
    filtre = sys.argv[2] if len(sys.argv) > 2 else None

    session = get_session()
    idtroll = get_troll_id(session)
    raw = fetch_category(session, idtroll, categorie)
    entries = parse_entries(raw)

    if filtre:
        needle = filtre.lower()
        entries = [e for e in entries if needle in e["nom"].lower()]

    print(json.dumps(entries, ensure_ascii=False, indent=2))
