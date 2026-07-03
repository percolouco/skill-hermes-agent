"""Lit et decrit le lieu actuel du troll, en extrayant proprement (via BeautifulSoup)
la description ET les formulaires d'action disponibles.

Usage:
    python3 mh_lieu.py [type] [id] [service]

Par defaut : type=L id=-3 service=0 (lieu actuel du troll).

Sortie : un JSON structure sur stdout, avec les cles:
    - titre        : titre du lieu (ex: "Portail : [4366144] Portail de Teleportation")
    - description   : texte descriptif du lieu (hors menus/formulaires)
    - forms         : liste des formulaires d'action detectes, chacun avec:
        - action        : URL cible du formulaire
        - method        : GET ou POST
        - hidden_fields : dict des champs caches (type, id, cp, ...)
        - buttons       : liste des boutons soumission {name, value, label}

IMPORTANT pour l'agent qui utilise ce script : ne JAMAIS soumettre un des
formulaires listes ici sans confirmation explicite de Perco. Chaque formulaire
represente une action qui coute des Points d'Action (PA) ou a un effet en jeu.
"""
import json
import sys

from bs4 import BeautifulSoup

from mh_common import BASE, get_session


def fetch_lieu(session, type_="L", id_="-3", service="0"):
    r = session.get(
        f"{BASE}/Play_a_Action.php",
        params={"type": type_, "id": id_, "service": service},
    )
    return r.text


def parse_lieu(html):
    # Titre + description : on part d'une copie du HTML dont on retire nav/forms/scripts
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    h2 = main.find("h2")
    titre = h2.get_text(strip=True) if h2 else None

    for tag in main.find_all(["nav", "form", "script", "style"]):
        tag.decompose()
    description = main.get_text("\n", strip=True)

    # Formulaires : sur une deuxieme copie intacte du HTML
    soup2 = BeautifulSoup(html, "html.parser")
    forms = []
    for form in soup2.find_all("form"):
        hidden = {
            inp.get("name"): inp.get("value", "")
            for inp in form.find_all("input", type="hidden")
            if inp.get("name")
        }
        buttons = []
        for btn in form.find_all(["button", "input"]):
            if btn.name == "button" or btn.get("type") == "submit":
                label = btn.get_text(strip=True) if btn.name == "button" else btn.get("value", "")
                buttons.append({
                    "name": btn.get("name"),
                    "value": btn.get("value", ""),
                    "label": label,
                })
        forms.append({
            "action": form.get("action"),
            "method": (form.get("method") or "get").upper(),
            "hidden_fields": hidden,
            "buttons": buttons,
        })

    return {"titre": titre, "description": description, "forms": forms}


if __name__ == "__main__":
    type_ = sys.argv[1] if len(sys.argv) > 1 else "L"
    id_ = sys.argv[2] if len(sys.argv) > 2 else "-3"
    service = sys.argv[3] if len(sys.argv) > 3 else "0"

    session = get_session()
    html = fetch_lieu(session, type_, id_, service)
    data = parse_lieu(html)
    print(json.dumps(data, ensure_ascii=False, indent=2))
