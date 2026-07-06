"""Lance une action a cible (sort/attaque speciale) sur un monstre/troll de la
case courante : Vampirisme, Griffe du Sorcier, etc. (cf. table ai_ToDo dans
../mh/LLM_TUTORIAL.md).

Flux (different de mh_submit.py, qui lui rejoue un <form> vu sur une page
"Lieu" classique) :
  1. GET Play_action.php?as_Action=ACTION!&ai_ToDo=<id> -> redirige (302) vers
     Play_a_Action.php?type=S&id=<id_sort>, qui affiche un <select name="id_target">
     des cibles sur la case.
  2. Filtre les cibles par un sous-texte de leur libellé (insensible a la casse).
  3. Lit le token anti-CSRF `cp` (change a chaque chargement, jamais reutiliser
     un ancien token).
  4. Si --execute : POST Play_a_ActionResult.php avec id_target + cp (consomme
     des PA reellement). Sinon (dry-run par defaut) : affiche juste ce qui
     serait fait, ne soumet rien.

Usage:
    python3 mh_action_target.py <ai_ToDo> "<sous-texte de la cible>" [--execute]

Exemple (Vampirisme = ai_ToDo 203, sur un monstre "sphynx") :
    python3 mh_action_target.py 203 "sphynx" --dry-run
    python3 mh_action_target.py 203 "sphynx" --execute

REGLE ABSOLUE : ne jamais appeler avec --execute sans un "oui" explicite et
recent de Perco pour CETTE cible precise. --execute consomme reellement des
PA en jeu (irreversible).
"""
import json
import sys

from bs4 import BeautifulSoup

from mh_common import BASE, get_session


def load_target_page(session, ai_todo):
    r = session.get(
        f"{BASE}/Play_action.php",
        params={"as_Action": "ACTION!", "ai_ToDo": str(ai_todo)},
        allow_redirects=True,
    )
    soup = BeautifulSoup(r.text, "html.parser")

    cp_input = soup.find("input", {"name": "cp"})
    type_input = soup.find("input", {"name": "type"})
    id_input = soup.find("input", {"name": "id"})
    select = soup.find("select", {"name": "id_target"})

    if not select:
        return {"erreur": "Aucun <select name='id_target'> trouve sur la page de cible", "html_extrait": r.text[:1500]}, None

    cibles = [
        (o["value"], o.get_text(strip=True))
        for o in select.find_all("option")
        if o.get("value")
    ]

    info = {
        "cp": cp_input["value"] if cp_input else None,
        "type": type_input["value"] if type_input else None,
        "id": id_input["value"] if id_input else None,
        "cibles": [{"value": v, "label": l} for v, l in cibles],
    }
    return info, r.text


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 mh_action_target.py <ai_ToDo> \"sous-texte cible\" [--execute]", file=sys.stderr)
        sys.exit(1)

    ai_todo = sys.argv[1]
    needle = sys.argv[2].lower()
    execute = "--execute" in sys.argv

    session = get_session()
    info, raw_html = load_target_page(session, ai_todo)

    if "erreur" in info:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        sys.exit(1)

    matches = [c for c in info["cibles"] if needle in c["label"].lower()]

    if not matches:
        print(json.dumps({
            "erreur": f"Aucune cible ne contient '{sys.argv[2]}'",
            "cibles_disponibles": info["cibles"],
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    target = matches[0]

    if not execute:
        print(json.dumps({
            "dry_run": True,
            "action_type": info["type"],
            "action_id": info["id"],
            "cible_choisie": target,
            "cp": info["cp"],
            "message": "Rien soumis (pas de --execute). Confirme avec Perco avant de relancer avec --execute.",
        }, ensure_ascii=False, indent=2))
        sys.exit(0)

    payload = {
        "as_Action": "ACTION !!",
        "type": info["type"],
        "id": info["id"],
        "id_target": target["value"],
        "cp": info["cp"],
    }
    r = session.post(f"{BASE}/Play_a_ActionResult.php", data=payload)

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup.find_all(["nav", "script", "style"]):
        tag.decompose()
    main = soup.find("main") or soup

    print(json.dumps({
        "cible_visee": target,
        "resultat": main.get_text("\n", strip=True),
    }, ensure_ascii=False, indent=2))
