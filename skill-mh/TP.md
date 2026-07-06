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
- `mh_vue.py` / `mh_move_toward.py` — voir section 3 ci-dessous (déplacement
  vers une cible visible dans la Vue).

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

## 3. Skill "Se déplacer vers une cible" (Déplacement Éclair)

Fichiers additionnels :
- `mh_vue.py` — liste les monstres (ou trolls/trésors/champignons/lieux)
  visibles dans la Vue du troll, triés par distance, filtrables par nom.
  Usage : `.venv/bin/python3 mh_vue.py monstres "Djinn"`
- `mh_move_toward.py` — calcule le trajet en compétence **Déplacement Éclair**
  (`ai_ToDo=112`) pour s'approcher d'une cible trouvée par `mh_vue.py`, et
  ne l'exécute QUE si demandé explicitement (`--execute`).

Le Déplacement Éclair déplace le troll d'au plus 1 case sur X, Y **et** N en
une seule utilisation (1 PA, +1 PA si le N/noeud change ce pas-ci). Il faut
donc plusieurs utilisations successives pour s'approcher d'une cible loin.

### Cycle pour "va vers X" (ex: "le Djinn le plus proche")

**Étape A — Calculer le plan (sans rien soumettre)**
```bash
.venv/bin/python3 mh_move_toward.py "Djinn" --dry-run
```
Renvoie un JSON : position actuelle, cible trouvée (la plus proche dont le nom
contient le filtre), `nb_pas` nécessaires pour arriver adjacent à la cible, et
`pa_estime` (coût total en Points d'Action).

**Étape B — Rapporter à Perco et demander confirmation**
> "Le [nom de la cible] le plus proche est à [dist] cases (position X,Y,N).
> Il faudrait [nb_pas] utilisations de Déplacement Éclair, pour un coût
> d'environ [pa_estime] PA. Veux-tu que je m'en approche ?"

**Étape C — Attendre le "oui" explicite**, comme pour toute autre action.

**Étape D — Si confirmé, exécuter réellement**
```bash
.venv/bin/python3 mh_move_toward.py "Djinn" --execute
```
Le script relit un token `cp` frais à chaque pas (obligatoire, le token
change à chaque chargement), s'arrête dès que la cible devient adjacente ou
si un pas échoue (PA insuffisants, etc.), et renvoie le résultat de chaque
pas. Résume ce résultat à Perco.

**Piège rencontré en le testant** : la page "Lieu" (`Play_a_Action.php?
type=L`) ne renvoie AUCUNE position quand le troll n'est pas sur un lieu
spécial (elle affiche juste "Vous n'êtes pas sur un lieu"). La position
fiable dans tous les cas vient de `Play_vue2.php`, attribut
`data-position="{...}"` sur `<li id="position">` — c'est ce que `mh_move_toward.py`
utilise (`get_position()`).

**Autre piège** : l'API `json_vue.php` qui liste monstres/trolls/trésors
renvoie la chaîne littérale `"KO"` (pas du JSON) si les en-têtes
`X-Requested-With: XMLHttpRequest` et `Referer` (vers `Play_vue2.php`) ne
sont pas envoyés.

**Limite connue** : `dist` (distance de Chebyshev sur X/Y, renvoyée par
`mh_vue.py`) ne tient pas compte du N (noeud/dimension) — le coût réel en PA
peut donc être supérieur au nombre de pas si N diffère beaucoup, chaque pas
changeant N coûtant 1 PA de plus.

---

## 4. Skill "Lancer un sort/attaque spéciale sur une cible" (ex: Vampirisme)

Fichier additionnel : `mh_action_target.py`.

Certaines actions (sorts, attaques spéciales) ne sont pas de simples boutons
sur la page "Lieu" : elles redirigent vers une page intermédiaire qui affiche
un `<select name="id_target">` listant les cibles disponibles sur la case
(monstres et/ou trolls). Le flux est différent de `mh_submit.py` (qui rejoue
un `<form>` classique) — voir `../mh/LLM_TUTORIAL.md` section 6 pour le détail
HTTP complet.

Table des `ai_ToDo` connus (identifiant numérique de l'action) :

| ai_ToDo | Action | PA |
|---|---|---|
| `3` | Attaque Normale | 4 |
| `107` | Frénésie | 6 |
| `149` | Lancer de Créatures | 4 |
| `203` | Vampirisme | 4 |
| `228` | Griffe du Sorcier | 4 |

### Cycle pour "lance [sort] sur [cible]"

**Étape A — Vérifier la cible (sans rien soumettre)**
```bash
.venv/bin/python3 mh_action_target.py <ai_ToDo> "sous-texte de la cible"
```
Exemple : `.venv/bin/python3 mh_action_target.py 203 "sphinx"`

Renvoie un JSON `dry_run: true` avec la cible trouvée (recherche insensible à
la casse et aux accents approximatifs — si aucun résultat, le script renvoie
la liste de toutes les cibles présentes sur la case pour comparaison, utile
si Perco s'est trompé d'orthographe, ex. "sphynx" au lieu de "Sphinx").

**Étape B — Rapporter à Perco et demander confirmation**
> "Je vois **[cible_choisie.label]** sur la case. Veux-tu que je lance
> [nom du sort] dessus (coût [PA] PA) ?"

**Étape C — Attendre le "oui" explicite**, comme pour toute autre action.

**Étape D — Si confirmé, exécuter réellement**
```bash
.venv/bin/python3 mh_action_target.py <ai_ToDo> "sous-texte de la cible" --execute
```
Le script relit une page fraîche (token `cp` à jour) avant de soumettre.
Renvoie le texte complet du résultat du jeu (réussite/échec, dégâts, PX
gagnés, PA consommés). Résume ce résultat à Perco.

**Piège évité** : ne jamais chercher la cible "à l'œil" dans un texte déjà lu
précédemment — toujours relire une page fraîche juste avant `--execute`, le
token `cp` change à chaque chargement et une cible peut disparaître/changer
entre deux tours si un monstre a bougé ou est mort entre-temps.

**Testé et validé le 2026-07-06** : Vampirisme (`ai_ToDo=203`) sur "un Sphinx
[Adulte]" — sortilège réussi (jet 60/85%), cible touchée (130 vs esquive 72),
108 dégâts infligés (100 PV réels après armure), 2 PX gagnés, 4 PA dépensés.

---

## Référence complémentaire

Le repo `mh` (projet compagnon MountyHall de Perco, plus large) contient
`LLM_TUTORIAL.md` avec le détail des endpoints du jeu (Play_menu, Play2,
sélection de cibles pour les sorts, table des `ai_ToDo` connus type
Attaque/Vampirisme/etc.). Utile si Perco demande d'étendre ce skill à d'autres
pages que "Lieu".
