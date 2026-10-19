"""Vérifie qu'une réponse d'IA est sourcée : chaque citation doit exister dans le document.

Trois statuts par citation :
  - exact        : la citation apparaît telle quelle dans le document (après normalisation) ;
  - approximate  : une phrase très proche existe (faute de frappe, mot changé) : à relire ;
  - missing      : rien de comparable dans le document : citation probablement inventée.

Limite assumée : l'outil vérifie que la citation EXISTE, pas que la réponse l'interprète correctement.
"""
import argparse
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher

APPROX_THRESHOLD = 0.9


def normalize(text):
    """Minuscules, sans accents, apostrophes et tirets unifiés, espaces réduits à un seul."""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[’‘ʼ]", "'", t)
    t = re.sub(r"[–—]", "-", t)
    return " ".join(t.split())


def best_similarity(document_norm, quote_norm):
    """Meilleure ressemblance (0 à 1) entre la citation et un passage du document de même longueur."""
    doc_words, quote_words = document_norm.split(), quote_norm.split()
    if not doc_words or not quote_words:
        return 0.0
    best = 0.0
    for size in {max(1, len(quote_words) - 1), len(quote_words), len(quote_words) + 1}:
        for start in range(0, max(1, len(doc_words) - size + 1)):
            candidate = " ".join(doc_words[start:start + size])
            best = max(best, SequenceMatcher(None, quote_norm, candidate).ratio())
    return best


def check_citation(document, citation, approx_threshold=APPROX_THRESHOLD):
    doc, quote = normalize(document), normalize(citation)
    if not quote:
        return {"citation": citation, "status": "missing", "similarity": 0.0}
    if quote in doc:
        return {"citation": citation, "status": "exact", "similarity": 1.0}
    similarity = round(best_similarity(doc, quote), 2)
    status = "approximate" if similarity >= approx_threshold else "missing"
    return {"citation": citation, "status": status, "similarity": similarity}


def verify_citations(document, citations):
    """Retourne {"found": [...], "missing": [...]} (exactes seulement, ordre d'origine conservé)."""
    found, missing = [], []
    for c in citations:
        (found if check_citation(document, c)["status"] == "exact" else missing).append(c)
    return {"found": found, "missing": missing}


def score(document, citations):
    """Part de citations exactes, arrondie à 2 décimales. Sans citation : 0.0 (pas de source)."""
    if not citations:
        return 0.0
    return round(len(verify_citations(document, citations)["found"]) / len(citations), 2)


def verify_answer(document, answer):
    """answer = {"text": "...", "citations": [...]}. Sourcée = au moins une citation, toutes exactes."""
    citations = answer.get("citations", [])
    results = [check_citation(document, c) for c in citations]
    exact = [r for r in results if r["status"] == "exact"]
    return {
        "sourced": bool(results) and len(exact) == len(results),
        "score": round(len(exact) / len(results), 2) if results else 0.0,
        "missing": [r["citation"] for r in results if r["status"] == "missing"],
        "approximate": [r["citation"] for r in results if r["status"] == "approximate"],
        "results": results,
    }


def closest_sentence(document, citation):
    """Phrase du document la plus proche de la citation : (phrase d'origine, ressemblance 0 à 1)."""
    sentences = [s.strip() for s in re.split(r"\n+|(?<=[.!?;])\s+", document) if s.strip()]
    quote = normalize(citation)
    best, best_score = "", 0.0
    for s in sentences:
        ratio = SequenceMatcher(None, quote, normalize(s)).ratio()
        if ratio > best_score:
            best, best_score = s, ratio
    return best, round(best_score, 2)


def word_key(word):
    """Mot normalisé sans ponctuation de bord : « mois, » et « mois » ne sont pas une différence."""
    return re.sub(r"^\W+|\W+$", "", normalize(word))


def diff_words(citation, passage):
    """Compare mot à mot. Retourne deux listes de (mot, différent?) : côté citation, côté document."""
    a, b = citation.split(), passage.split()
    ops = SequenceMatcher(None, [word_key(w) for w in a], [word_key(w) for w in b]).get_opcodes()
    left, right = [], []
    for tag, i1, i2, j1, j2 in ops:
        # la fin de la phrase du document que la citation n'a pas reprise n'est pas une différence
        changed = tag != "equal" and not (tag == "insert" and j2 == len(b))
        left += [(w, changed) for w in a[i1:i2]]
        right += [(w, changed) for w in b[j1:j2]]
    return left, right


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vérifie qu'une réponse d'IA est sourcée.")
    parser.add_argument("document", help="fichier texte du document source")
    parser.add_argument("answer", help="fichier JSON : {\"text\": ..., \"citations\": [...]}")
    args = parser.parse_args(argv)
    with open(args.document, encoding="utf-8") as f:
        document = f.read()
    with open(args.answer, encoding="utf-8") as f:
        answer = json.load(f)
    report = verify_answer(document, answer)
    icons = {"exact": "OK         ", "approximate": "À RELIRE   ", "missing": "INTROUVABLE"}
    for r in report["results"]:
        print(f"[{icons[r['status']]}] ({r['similarity']:.2f}) {r['citation']}")
    print(f"\nScore : {report['score']}  |  Réponse sourcée : {'oui' if report['sourced'] else 'NON'}")
    return 0 if report["sourced"] else 1


if __name__ == "__main__":
    sys.exit(main())
