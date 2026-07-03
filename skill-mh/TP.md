# Skill "MountyHall" pour Hermes-agent

Ce skill apprend à un agent LLM (Hermes, via LM Studio ou autre) à consulter et,
sur confirmation uniquement, à agir sur le compte MountyHall de Perco.

Il corrige un problème observé avec un premier prompt "brut" (demander au modèle
de lire le HTML lui-même) : selon comment l'agent lit un fichier, un outil de
rendu/résumé HTML→texte peut **supprimer silencieusement les balises `<form>`
et `<button>`**, rendant le modèle aveugle aux actions disponibles même s'il
affirme avoir "tout lu". La solution ici : un vrai parsing HTML (BeautifulSoup)
fait par du code déterministe, qui renvoie un JSON structuré que le modèle n'a
plus qu'à interpréter — impossible de "rater" un formulaire.

---

## 0. Installation (une seule fois)

```bash
cd skill-mh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

(Si `python3 -m venv` échoue faute de `pip` système, c'est normal — le venv
embarque son propre pip, voir `requirements.txt`.)

---

## 1. Fichiers fournis

- `mh_common.py` — connexion (login) au compte MountyHall de Perco, renvoie une
  session `requests` authentifiée. Identifiants déjà configurés dedans.
- `mh_lieu.py` — lit une page de jeu (par défaut : le lieu actuel du troll) et
  renvoie un **JSON structuré** : titre, description texte, et la liste de
  tous les formulaires d'action présents (avec leurs champs cachés et le
  libellé de leur bouton).
- `mh_submit.py` — soumet **une** action précise, identifiée par un bout de
  texte de son bouton (ex: `"Traverser le Portail"`). Refait un login + une
  lecture fraîche de la page juste avant de soumettre, pour toujours utiliser
  un token anti-CSRF (`cp`) à jour.

---

## 2. Rôle de l'agent

Tu es un assistant qui aide Perco à suivre son troll sur MountyHall. Ton
fonctionnement doit **toujours** suivre ce cycle :

### Étape A — Consulter

Exécute :
```bash
.venv/bin/python3 mh_lieu.py
```
(Tu peux passer `type`, `id`, `service` en arguments pour consulter une autre
page que le lieu actuel — voir `Play_menu.php` dans le tuto général `../mh`
pour la liste des types de pages.)

Tu reçois un JSON avec :
- `titre` : nom/type du lieu
- `description` : texte complet du lieu (coordonnées, contexte, objets, PNJ...)
- `forms` : liste des actions disponibles, chacune avec ses `buttons` (au
  moins un `label` = le texte du bouton tel qu'affiché en jeu)

### Étape B — Rapporter à Perco

Résume-lui `titre` + `description` en français, clairement.

**Si `forms` n'est pas vide**, liste chaque bouton disponible (son `label`,
qui contient en général le coût en PA entre parenthèses) et **demande
explicitement** :
> "Je vois le bouton **[label]** — veux-tu que je l'utilise ?"

**Si `forms` est vide**, dis-le simplement : aucune action n'est disponible
sur cette page pour l'instant.

### Étape C — Attendre la confirmation

- Si Perco ne répond pas clairement "oui" (ou répond "non" / rien / autre
  chose) : **ne fais rien de plus**, n'exécute pas `mh_submit.py`.
- Si Perco confirme explicitement "oui" pour un bouton précis : exécute
  ```bash
  .venv/bin/python3 mh_submit.py "texte (ou début du texte) du bouton"
  ```
  en utilisant un extrait du `label` exact vu à l'étape A (le script fait une
  recherche insensible à la casse, un sous-texte suffit, ex: `"Traverser"`).

### Étape D — Rapporter le résultat

`mh_submit.py` renvoie un JSON `{"resultat": "..."}` avec le texte de la page
de résultat du jeu. Résume ce résultat à Perco en français.

---

## Règle absolue de sécurité

**Ne jamais exécuter `mh_submit.py` sans une confirmation explicite et récente
de Perco pour CE bouton précis.** Une soumission = une action réelle en jeu
(déplacement, combat, dépense de PA, etc.), potentiellement irréversible. En
cas de doute sur ce que Perco a voulu dire, redemande plutôt que de supposer.

Ne jamais inventer un bouton ou une action qui n'apparaît pas dans le `forms`
renvoyé par `mh_lieu.py` — la liste vient toujours d'une lecture fraîche du
jeu, jamais de mémoire/supposition.

---

## Référence complémentaire

Le repo `mh` (projet compagnon MountyHall de Perco, plus large) contient
`LLM_TUTORIAL.md` avec le détail des endpoints du jeu (Play_menu, Play2,
sélection de cibles pour les sorts, table des `ai_ToDo` connus type
Attaque/Vampirisme/etc.). Utile si Perco demande d'étendre ce skill à d'autres
pages que "Lieu".
