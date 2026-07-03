"""Soumet UNE action precise vue sur la page du lieu (ou toute autre page type/id),
identifiee par un extrait du texte de son bouton.

Ce script refait un login + une lecture FRAICHE de la page avant de soumettre,
pour toujours utiliser un token anti-CSRF (`cp`) a jour (il change a chaque
chargement de page - reutiliser un ancien token fait echouer l'action).

Usage:
    python3 mh_submit.py "texte du bouton" [type] [id] [service]

Exemple:
    python3 mh_submit.py "Traverser le Portail"
    python3 mh_submit.py "Attaquer" A -6

REGLE ABSOLUE : ce script ne doit JAMAIS etre appele par l'agent sans que
Perco ait dit explicitement "oui" a la question "veux-tu que j'utilise le
bouton [X] ?". Une soumission = une action reelle en jeu (PA depenses,
deplacement, combat...). En cas de doute, ne pas executer.
"""
import json
import sys

from bs4 import BeautifulSoup

from mh_common import BASE, get_session
from mh_lieu import fetch_lieu, parse_lieu


def find_form_by_label(forms, label_substring):
    needle = label_substring.lower()
    for form in forms:
        for btn in form["buttons"]:
            if needle in (btn["label"] or "").lower():
                return form, btn
    return None, None


def resolve_action_url(action):
    if action.startswith("http"):
        return action
    if action.startswith("/"):
        return "https://mh2.mh.raistlin.fr" + action
    return f"{BASE}/{action}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 mh_submit.py \"texte du bouton\" [type] [id] [service]", file=sys.stderr)
        sys.exit(1)

    label = sys.argv[1]
    type_ = sys.argv[2] if len(sys.argv) > 2 else "L"
    id_ = sys.argv[3] if len(sys.argv) > 3 else "-3"
    service = sys.argv[4] if len(sys.argv) > 4 else "0"

    session = get_session()
    html = fetch_lieu(session, type_, id_, service)
    data = parse_lieu(html)

    form, btn = find_form_by_label(data["forms"], label)
    if not form:
        print(json.dumps({
            "erreur": f"Aucun bouton contenant '{label}' trouve sur cette page",
            "forms_disponibles": data["forms"],
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    payload = dict(form["hidden_fields"])
    if btn["name"]:
        payload[btn["name"]] = btn["value"]

    action_url = resolve_action_url(form["action"])
    method = form["method"]

    if method == "POST":
        r = session.post(action_url, data=payload)
    else:
        r = session.get(action_url, params=payload)

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup.find_all(["nav", "script", "style"]):
        tag.decompose()
    main = soup.find("main") or soup
    print(json.dumps({"resultat": main.get_text("\n", strip=True)}, ensure_ascii=False, indent=2))
