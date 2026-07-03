"""Connexion partagee au jeu MountyHall (compte de Perco)."""
import requests

BASE = "https://mh2.mh.raistlin.fr/mountyhall/MH_Play"
LOGIN = "Perco"
PASSWORD = "taotd"


def get_session():
    """Se connecte et renvoie une requests.Session authentifiee (cookie PHPSESSID)."""
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    r = s.post(
        f"{BASE}/PlayStart2.php",
        data={
            "as_Login": LOGIN,
            "as_Pwd": PASSWORD,
            "ai_design": "30",
            "as_Action": "login",  # obligatoire, sinon le serveur reaffiche juste le formulaire
        },
    )
    if "Bienvenue" not in r.text:
        raise RuntimeError("Echec de connexion MountyHall - identifiants invalides ou serveur indisponible")
    return s
