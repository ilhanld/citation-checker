"""Interface web locale du vérificateur de citations (bibliothèque standard uniquement).

Lancer : python3 app.py  -> http://127.0.0.1:8765
Le texte saisi reste sur ta machine : le serveur n'écoute que sur 127.0.0.1.
"""
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from citation_checker import check_citation, closest_sentence, diff_words, verify_answer

HOST, PORT = "127.0.0.1", 8765
HERE = Path(__file__).parent


def analyse(document, citations):
    """Rapport JSON : le verdict global et, pour chaque citation, la phrase proche et la différence."""
    report = verify_answer(document, {"citations": citations})
    for r in report["results"]:
        if r["status"] == "approximate":
            passage, _ = closest_sentence(document, r["citation"])
            left, right = diff_words(r["citation"], passage)
            r["passage"] = passage
            r["diff_citation"] = left
            r["diff_passage"] = right
    return report


BAIL = ("Le locataire verse un loyer de 900 euros par mois. "
        "Le bail dure trois ans à compter du 1er janvier 2026. "
        "Le dépôt de garantie est de 1 800 euros.")


def with_sources(text, citations):
    """Réponse d'IA complète : un texte, puis ses sources entre guillemets."""
    return text + "\n\nSources :\n" + "\n".join(f"« {c} »" for c in citations)


def load_examples():
    """Exemples prédéfinis : le premier vient des fichiers du dossier examples/, les autres sont courts."""
    acte = (HERE / "examples" / "acte_vente.txt").read_text(encoding="utf-8")
    inventee = json.loads((HERE / "examples" / "reponse_inventee.json").read_text(encoding="utf-8"))
    ok = json.loads((HERE / "examples" / "reponse_ok.json").read_text(encoding="utf-8"))
    return [
        {"name": "Bail : exemple simple (un montant modifié)", "document": BAIL,
         "answer": with_sources("Le dépôt de garantie est de 2 000 euros.",
                                ["Le locataire verse un loyer de 900 euros par mois.",
                                 "Le dépôt de garantie est de 2 000 euros."])},
        {"name": "Acte de vente : une date modifiée (2027 devenu 2028)", "document": acte,
         "answer": with_sources(inventee["text"], inventee["citations"])},
        {"name": "Acte de vente : toutes les citations sont exactes", "document": acte,
         "answer": with_sources(ok["text"], ok["citations"])},
        {"name": "Bail : citations entièrement inventées", "document": BAIL,
         "answer": with_sources("Le locataire peut sous-louer.",
                                ["Le locataire peut sous-louer librement le logement.",
                                 "Le préavis de départ est de huit jours."])},
    ]


PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vérificateur de citations</title>
<style>
  :root { --bg:#faf9f6; --fg:#1d1d1b; --card:#fff; --line:#ddd9d0; --ok:#1f7a3d; --warn:#b36b00; --ko:#b3261e; }
  @media (prefers-color-scheme: dark) { :root { --bg:#161614; --fg:#efede8; --card:#201f1c; --line:#3a3833; } }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui,sans-serif; }
  main { max-width:960px; margin:0 auto; padding:24px 16px 64px; }
  h1 { font-size:1.4rem; margin:0 0 4px; } p.sub { margin:0 0 20px; opacity:.75; }
  .cols { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  @media (max-width:700px) { .cols { grid-template-columns:1fr; } }
  label { display:block; font-weight:600; margin-bottom:6px; }
  textarea, input[type=text] { width:100%; padding:10px; font:inherit; color:inherit; background:var(--card);
             border:1px solid var(--line); border-radius:8px; }
  textarea { min-height:240px; resize:vertical; }
  .actions { margin:16px 0; display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
  select, button { font:inherit; padding:8px 16px; border-radius:8px; border:1px solid var(--line); background:var(--card);
           color:inherit; cursor:pointer; } button.main { background:var(--fg); color:var(--bg); border-color:var(--fg); }
  details { margin-bottom:16px; } summary { cursor:pointer; opacity:.8; }
  details .actions { margin:10px 0 4px; } .hint { font-size:.85rem; opacity:.75; margin:6px 0 0; }
  .verdict { padding:12px 16px; border-radius:8px; font-weight:600; margin-bottom:12px; border:1px solid var(--line); }
  .verdict.yes { color:var(--ok); } .verdict.no { color:var(--ko); }
  .item { background:var(--card); border:1px solid var(--line); border-left-width:6px; border-radius:8px;
          padding:10px 14px; margin-bottom:10px; }
  .item.exact { border-left-color:var(--ok); } .item.approximate { border-left-color:var(--warn); }
  .item.missing { border-left-color:var(--ko); }
  .tag { font-size:.8rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
  .exact .tag { color:var(--ok); } .approximate .tag { color:var(--warn); } .missing .tag { color:var(--ko); }
  .cmp { margin-top:8px; font-size:.95rem; } .cmp small { opacity:.7; display:block; }
  mark { background:rgba(179,38,30,.25); color:inherit; border-radius:3px; padding:0 2px; }
  footer { margin-top:32px; font-size:.85rem; opacity:.7; }
</style></head><body><main>
<h1>Vérificateur de citations</h1>
<p class="sub">Colle un document et la réponse d'une IA. L'outil vérifie que les passages qu'elle cite entre guillemets existent vraiment dans le document.</p>
<div class="cols">
  <div><label for="doc">1. Le document</label><textarea id="doc"></textarea></div>
  <div><label for="ans">2. La réponse de l'IA (avec ses citations entre guillemets)</label><textarea id="ans"></textarea></div>
</div>
<div class="actions">
  <button class="main" id="go">Vérifier</button>
  <select id="ex" aria-label="Exemples prédéfinis"><option value="">Charger un exemple...</option></select>
</div>
<details>
  <summary>Je n'ai pas encore de réponse d'IA</summary>
  <label for="q" style="margin-top:10px">Ta question sur le document</label>
  <input type="text" id="q" placeholder="Ex. : Quel est le montant du dépôt de garantie ?">
  <div class="actions">
    <button id="askClaude">Demander à Claude</button>
    <button id="askGpt">Demander à ChatGPT</button>
    <button id="copyPrompt">Copier le prompt</button>
  </div>
  <p class="hint" id="askHint">Le document part chez l'IA choisie seulement quand tu cliques sur l'un de ces boutons. Copie ensuite sa réponse dans le champ 2.</p>
</details>
<div id="out" aria-live="polite"></div>
<footer>L'outil vérifie que les citations existent, pas que la réponse les interprète correctement.</footer>
</main>
<script>
const $ = id => document.getElementById(id);
const LABEL = { exact: "Exacte", approximate: "À relire", missing: "Introuvable" };
const esc = s => s.replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const words = pairs => pairs.map(([w, changed]) => changed ? "<mark>" + esc(w) + "</mark>" : esc(w)).join(" ");

function extractQuotes(text) {
  const found = [], re = /«\s*([^»]+?)\s*»|“([^”]+)”|"([^"]+)"/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const quote = (m[1] || m[2] || m[3] || "").trim();
    if (quote.length >= 15 && !found.includes(quote)) found.push(quote);
  }
  return found;
}

function render(report) {
  let html = '<div class="verdict ' + (report.sourced ? "yes" : "no") + '">' +
    (report.sourced ? "Réponse sourcée" : "Réponse NON sourcée") + " - score " + report.score + "</div>";
  for (const r of report.results) {
    html += '<div class="item ' + r.status + '"><span class="tag">' + LABEL[r.status] +
      " (" + r.similarity.toFixed(2) + ")</span><div>" + esc(r.citation) + "</div>";
    if (r.status === "missing") {
      html += '<div class="cmp"><small>Aucune phrase comparable dans le document.</small></div>';
    } else if (r.status === "approximate") {
      html += '<div class="cmp"><small>Citation</small>' + words(r.diff_citation) +
        "<small>Phrase la plus proche du document</small>" + words(r.diff_passage) + "</div>";
    }
    html += "</div>";
  }
  $("out").innerHTML = html;
}

$("go").onclick = async () => {
  const citations = extractQuotes($("ans").value);
  if (!citations.length) {
    $("out").innerHTML = '<div class="verdict no">Aucune citation entre guillemets trouvée dans la réponse : elle n\'est donc pas sourcée.</div>';
    return;
  }
  const res = await fetch("/verify", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document: $("doc").value, citations }) });
  render(await res.json());
};

const MAX_URL = 6000;
function buildPrompt() {
  const q = $("q").value.trim() || "Résume les engagements essentiels de ce document.";
  return "Voici un document. Réponds à ma question en t'appuyant uniquement sur ce document, et cite entre guillemets « » " +
    "chaque passage exact (mot pour mot) sur lequel tu t'appuies.\n\nQuestion : " + q + "\n\nDocument :\n" + $("doc").value;
}
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch (e) { return false; }
}
async function ask(base) {
  if (!$("doc").value.trim()) { $("askHint").textContent = "Colle d'abord un document dans le champ 1."; return; }
  const prompt = buildPrompt(), url = base + encodeURIComponent(prompt);
  if (url.length <= MAX_URL) {
    window.open(url, "_blank", "noopener");
    $("askHint").textContent = "L'IA s'ouvre dans un nouvel onglet. Copie sa réponse et colle-la dans le champ 2.";
  } else {
    const ok = await copyText(prompt);
    window.open(base.split("?")[0], "_blank", "noopener");
    $("askHint").textContent = ok ? "Document trop long pour un lien : le prompt est copié, colle-le dans l'IA qui vient de s'ouvrir."
                                  : "Document trop long pour un lien : utilise « Copier le prompt » puis colle-le dans l'IA.";
  }
}
$("askClaude").onclick = () => ask("https://claude.ai/new?q=");
$("askGpt").onclick = () => ask("https://chatgpt.com/?q=");
$("copyPrompt").onclick = async () => {
  $("askHint").textContent = (await copyText(buildPrompt())) ? "Prompt copié." : "Copie impossible : sélectionne le texte à la main.";
};

let EXAMPLES = [];
fetch("/examples").then(r => r.json()).then(list => {
  EXAMPLES = list;
  list.forEach((e, i) => { const o = document.createElement("option"); o.value = i; o.textContent = e.name; $("ex").appendChild(o); });
  if (!$("doc").value && !$("ans").value && list.length) { $("ex").value = 0; $("ex").onchange(); }
});
$("ex").onchange = () => {
  const e = EXAMPLES[$("ex").value];
  if (!e) return;
  $("doc").value = e.document; $("ans").value = e.answer; $("go").click();
};
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, content_type, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self._send(PAGE, "text/html")
        elif self.path == "/examples":
            self._send(json.dumps(load_examples()), "application/json")
        else:
            self._send("Introuvable", "text/plain", 404)

    def do_POST(self):
        if self.path != "/verify":
            return self._send("Introuvable", "text/plain", 404)
        try:
            size = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(size))
            report = analyse(str(payload.get("document", "")), [str(c) for c in payload.get("citations", [])])
        except (ValueError, TypeError, AttributeError):
            return self._send(json.dumps({"error": "requête invalide"}), "application/json", 400)
        self._send(json.dumps(report), "application/json")

    def log_message(self, *args):
        pass


def main():
    server = HTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Interface disponible sur {url} (Ctrl+C pour arrêter)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêté.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
