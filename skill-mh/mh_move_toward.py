"""Calcule (et, seulement sur confirmation, execute) le trajet en 'Deplacement
Eclair' (competence, ai_ToDo=112) pour s'approcher d'une cible (monstre/troll/
tresor) trouvee par mh_vue.py.

Le Deplacement Eclair deplace le troll d'AU PLUS 1 case sur CHAQUE axe (X, Y,
N) a la fois, par utilisation (radio boutons -1/0/+1 sur Play_action.php?
as_Action=ACTION!&ai_ToDo=112). Une utilisation coute 1 PA ; +1 PA
supplementaire si le N (noeud/dimension) change lors de ce pas.

Usage (mode CALCUL SEUL, ne soumet rien) :
    python3 mh_move_toward.py "Djinn" --dry-run

Usage (mode EXECUTION, ne JAMAIS lancer sans confirmation explicite de Perco
pour CETTE cible precise) :
    python3 mh_move_toward.py "Djinn" --execute

Le script :
1. Recupere la position actuelle du troll (page Lieu).
2. Cherche la cible la plus proche dont le nom contient <filtre> (categorie
   'monstres' par defaut) via mh_vue.py.
3. Calcule le nombre de pas necessaires pour arriver ADJACENT a la cible
   (distance de Chebyshev <= 1 en X/Y), et le cout total en PA (en tenant
   compte du nombre de pas ou N change).
4. En --dry-run (ou par defaut) : affiche seulement le plan (JSON), ne
   soumet AUCUNE requete de deplacement.
5. En --execute : soumet les pas un par un (relit un token cp frais a
   chaque pas), s'arrete des que la cible est adjacente (dist<=1) ou si le
   nombre de pas prevus est atteint, et affiche le resultat de chaque pas.
"""
import json
import re
import sys

from mh_common import BASE, get_session
from mh_vue import fetch_category, get_troll_id, parse_entries

DE_TODO = "112"
DE_TYPE = "C"
DE_ID = "12"


def get_position(session):
    """Lit la position actuelle depuis Play_vue2.php (data-position sur <li id="position">).
    Contrairement a la page Lieu (Play_a_Action.php?type=L), cette page fonctionne
    meme quand le troll n'est PAS sur un lieu special ('Vous n'etes pas sur un lieu')."""
    r = session.get(f"{BASE}/Play_vue2.php")
    m = re.search(r'data-position="([^"]+)"', r.text)
    if not m:
        raise RuntimeError("Impossible de lire la position actuelle sur Play_vue2.php")
    import html as html_module
    pos = json.loads(html_module.unescape(m.group(1)))
    return pos["x"], pos["y"], pos["n"]


def sign(v):
    return (v > 0) - (v < 0)


def plan_route(x0, y0, n0, xt, yt, nt):
    """Renvoie la liste des pas (dx,dy,dn) a effectuer, un par appel de DE,
    jusqu'a etre adjacent (chebyshev X/Y <= 1). Chaque pas rapproche d'au
    plus 1 sur chaque axe simultanement."""
    steps = []
    x, y, n = x0, y0, n0
    while max(abs(xt - x), abs(yt - y)) > 1:
        dx = sign(xt - x)
        dy = sign(yt - y)
        dn = sign(nt - n)
        steps.append((dx, dy, dn))
        x, y, n = x + dx, y + dy, n + dn
        if len(steps) > 200:  # garde-fou anti boucle infinie
            break
    return steps


def estimate_pa(steps):
    total = 0
    for dx, dy, dn in steps:
        total += 1
        if dn != 0:
            total += 1
    return total


def fetch_de_form(session):
    """Recupere la page de la competence (token cp frais + valeurs radio actuelles)."""
    r = session.get(
        f"{BASE}/Play_action.php",
        params={"as_Action": "ACTION!", "ai_ToDo": DE_TODO},
    )
    m_cp = re.search(r'name="cp" value="([^"]+)"', r.text)
    if not m_cp:
        raise RuntimeError("Token cp introuvable sur la page Deplacement Eclair")
    return m_cp.group(1)


def submit_step(session, dx, dy, dn):
    cp = fetch_de_form(session)
    payload = {
        "as_Action": "ACTION !!",
        "type": DE_TYPE,
        "id": DE_ID,
        "cp": cp,
        "depl_x": str(dx),
        "depl_y": str(dy),
        "depl_n": str(dn),
    }
    r = session.post(f"{BASE}/Play_a_ActionResult.php", data=payload)
    return r.text


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 mh_move_toward.py \"filtre nom cible\" [--dry-run|--execute] [categorie]", file=sys.stderr)
        sys.exit(1)

    filtre = sys.argv[1]
    mode = "--dry-run"
    categorie = "monstres"
    for arg in sys.argv[2:]:
        if arg in ("--dry-run", "--execute"):
            mode = arg
        else:
            categorie = arg

    session = get_session()
    x0, y0, n0 = get_position(session)

    idtroll = get_troll_id(session)
    raw = fetch_category(session, idtroll, categorie)
    entries = parse_entries(raw)
    needle = filtre.lower()
    candidats = [e for e in entries if needle in e["nom"].lower()]

    if not candidats:
        print(json.dumps({"erreur": f"Aucune cible contenant '{filtre}' trouvee dans la Vue"}, ensure_ascii=False))
        sys.exit(1)

    cible = candidats[0]  # deja trie par dist croissante
    steps = plan_route(x0, y0, n0, cible["x"], cible["y"], cible["n"])
    pa_estime = estimate_pa(steps)

    plan = {
        "position_actuelle": {"x": x0, "y": y0, "n": n0},
        "cible": cible,
        "nb_pas": len(steps),
        "pa_estime": pa_estime,
        "pas_detailles": [{"depl_x": s[0], "depl_y": s[1], "depl_n": s[2]} for s in steps],
    }

    if mode == "--dry-run":
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        sys.exit(0)

    # --execute : soumet reellement les pas, un par un
    resultats = []
    for i, (dx, dy, dn) in enumerate(steps, 1):
        html_resultat = submit_step(session, dx, dy, dn)
        # texte simplifie du resultat (premieres lignes utiles)
        texte = re.sub(r"<[^>]+>", " ", html_resultat)
        texte = re.sub(r"\s+", " ", texte).strip()
        resultats.append({"pas": i, "depl": [dx, dy, dn], "resultat_resume": texte[:500]})
        # arret anticipe si le message indique un probleme (PA insuffisants, etc.)
        if "insuffisant" in texte.lower() or "erreur" in texte.lower():
            break

    print(json.dumps({"plan": plan, "execution": resultats}, ensure_ascii=False, indent=2))
