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

Ouvre `http://127.0.0.1:8765` : on colle un document et les citations (une par ligne), une liste d'exemples prédéfinis remplit les deux zones (date modifiée, montant modifié, citations inventées, tout exact). Chaque citation est classée exacte / à relire / introuvable, avec, pour les citations « à relire », la phrase la plus proche du document et le mot qui diffère surligné. Un bloc « Demander à une IA » ferme la boucle : on écrit une question, un bouton ouvre Claude ou ChatGPT avec le prompt déjà rempli (ou le copie si le document est trop long pour un lien), on recolle la réponse, et l'outil en extrait les passages entre guillemets pour les vérifier. Le texte du document ne part chez l'IA que si on clique sur l'un de ces boutons ; sinon, aucune dépendance (bibliothèque standard) et le serveur n'écoute que sur `127.0.0.1`.

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
