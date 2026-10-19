# citation-checker

Petit outil en Python qui vérifie qu'une réponse d'IA est **sourcée** : chaque citation doit exister dans le document.

Dans des domaines où l'on engage sa responsabilité (juridique, notarial, conformité), une réponse « plausible » ne suffit pas : elle doit être juste et traçable. Ce prototype automatise le premier contrôle : **la citation existe-t-elle vraiment dans le source ?**

## Exemple

```bash
python3 citation_checker.py examples/acte_vente.txt examples/reponse_inventee.json
```

```
[OK         ] (1.00) Le vendeur déclare que le bien est libre de toute hypothèque.
[À RELIRE   ] (0.98) Le bien est vendu occupé par un locataire jusqu'au 30 juin 2028.
[INTROUVABLE] (0.57) Le bien est vendu libre de toute occupation et sans servitude.

Score : 0.33  |  Réponse sourcée : NON
```

Le document source dit « 30 juin **2027** » : l'IA a changé l'année, et l'outil le signale (« à relire ») au lieu de l'accepter.

## Trois statuts par citation

| Statut | Sens |
|---|---|
| `exact` | la citation apparaît telle quelle dans le document (après normalisation) |
| `approximate` | une phrase très proche existe (similarité ≥ 0,9) : **à relire**, jamais validée automatiquement |
| `missing` | rien de comparable : citation probablement inventée |

Une réponse est « sourcée » seulement si elle a **au moins une citation et que toutes sont exactes**.

La normalisation ignore la casse, les accents, les apostrophes et tirets typographiques, et les espaces multiples.

## Utilisation en Python

```python
from citation_checker import verify_answer

report = verify_answer(document, {"text": "…", "citations": ["…", "…"]})
report["sourced"], report["score"], report["missing"], report["approximate"]
```

## Interface web (locale)

```bash
python3 app.py
```

Ouvre `http://127.0.0.1:8765`, en trois étapes :

1. **Le document** : on colle un texte, ou on charge un document d'exemple (fictif, écrit pour la démonstration, défini dans `examples/exemples.json` : on peut en ajouter sans toucher au code).
2. **Demander à une IA** : on écrit une question, un bouton ouvre Claude ou ChatGPT avec le prompt déjà rempli (ou le copie si le document est trop long pour un lien). Le document ne part chez l'IA que si on clique sur l'un de ces boutons.
3. **La réponse de l'IA** : on la colle, et « Vérifier les citations » repère les passages entre guillemets et classe chacun : exacte / à relire / introuvable. Pour les citations « à relire », la page montre la phrase la plus proche du document avec les mots qui diffèrent surlignés.

Aucune réponse d'IA n'est pré-écrite dans les exemples : la réponse vient d'une vraie IA, et le verdict est toujours calculé à partir de ce qui est dans les champs. Aucune dépendance (bibliothèque standard) ; le serveur n'écoute que sur `127.0.0.1`.

## Hébergement (Docker)

```bash
docker compose up -d --build
```

Le conteneur tourne sans droits root, en lecture seule, avec 256 Mo de mémoire maximum, et n'est publié que sur `127.0.0.1:8765` de la machine : c'est un proxy HTTPS (nginx) placé devant qui l'expose. Les textes reçus ne sont ni enregistrés ni journalisés, et des limites protègent le serveur (document : 40 000 caractères, 15 citations). Le texte collé est envoyé au serveur pour être vérifié : à ne pas utiliser avec des documents confidentiels.

Sans Docker : `NO_BROWSER=1 PORT=8765 python3 app.py`.

## Tests

```bash
python3 -m unittest -v
```

Aucune dépendance externe (bibliothèque standard uniquement).

## Limites

- L'outil vérifie que la citation **existe**, pas que la réponse l'**interprète correctement** : une citation exacte peut être mal utilisée.
- Comparaison textuelle seulement : pas de compréhension du sens, pas de gestion des documents scannés (OCR).
- La détection « approximative » compare des passages de longueur voisine ; sur de très gros documents, elle serait à optimiser.
- Les exemples sont fictifs. N'y mettez pas de documents réels.

## Transparence

Prototype réalisé avec l'aide d'un assistant IA (Claude Code), puis relu, testé et compris par l'auteur. Principe retenu : une citation « presque exacte » n'est jamais validée automatiquement, elle est signalée pour relecture.
