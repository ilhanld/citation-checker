"""Interface web locale du vérificateur de citations (bibliothèque standard uniquement).

Lancer : python3 app.py  -> http://127.0.0.1:8765
Par défaut, le serveur n'écoute que sur 127.0.0.1 : le texte saisi reste sur la machine.
Hébergement : HOST=0.0.0.0 PORT=8765 python3 app.py (derrière un proxy HTTPS). Les textes reçus ne sont ni
enregistrés ni journalisés.
"""
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from citation_checker import check_citation, closest_sentence, diff_words, verify_answer

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))
HERE = Path(__file__).parent

# Limites : la comparaison coûte environ 3 s par citation introuvable sur 67 000 caractères.
MAX_DOCUMENT_CHARS = 40_000
MAX_CITATIONS = 15
MAX_CITATION_CHARS = 1_000
MAX_BODY_BYTES = 200_000


def validate(document, citations):
    """Refuse les entrées trop grosses (site public). Lève ValueError avec un message affichable."""
    if len(document) > MAX_DOCUMENT_CHARS:
        raise ValueError(f"Document trop long ({len(document)} caractères, maximum {MAX_DOCUMENT_CHARS}).")
    if len(citations) > MAX_CITATIONS:
        raise ValueError(f"Trop de citations ({len(citations)}, maximum {MAX_CITATIONS}).")
    if any(len(c) > MAX_CITATION_CHARS for c in citations):
        raise ValueError(f"Une citation dépasse {MAX_CITATION_CHARS} caractères.")


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


def load_examples():
    """Documents d'exemple (fictifs) lus dans examples/exemples.json, avec une question suggérée.
    Aucune réponse d'IA n'est pré-écrite : elle vient d'une vraie IA ou du collage de l'utilisateur."""
    folder = HERE / "examples"
    entries = json.loads((folder / "exemples.json").read_text(encoding="utf-8"))
    return [{"name": e["name"], "question": e.get("question", ""),
             "document": (folder / e["document_file"]).read_text(encoding="utf-8")} for e in entries]


PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vérificateur de citations</title>
<style>
  :root { --bg:#f6f4ef; --fg:#1d1d1b; --muted:#6b6860; --card:#fff; --line:#e1ddd3; --accent:#2f3a56;
          --ok:#1f7a3d; --ok-bg:#e6f3ea; --warn:#9a5b00; --warn-bg:#fbf0dc; --ko:#b3261e; --ko-bg:#fbe7e5; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#141413; --fg:#efede8; --muted:#a09c92; --card:#1f1e1b; --line:#37352f; --accent:#8fa2d6;
            --ok:#6fcf8e; --ok-bg:#16301f; --warn:#f0b45a; --warn-bg:#33270f; --ko:#ff8a80; --ko-bg:#3a1b19; } }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 system-ui,-apple-system,sans-serif; }
  main { max-width:820px; margin:0 auto; padding:32px 16px 72px; }
  header { margin-bottom:24px; }
  h1 { font-size:1.6rem; margin:0 0 6px; letter-spacing:-.01em; }
  .sub { margin:0; color:var(--muted); max-width:62ch; }
  .step { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px 20px; margin-bottom:16px; }
  .step h2 { font-size:1.05rem; margin:0 0 12px; display:flex; align-items:center; gap:10px; }
  .n { display:inline-grid; place-items:center; width:26px; height:26px; border-radius:50%; background:var(--accent);
       color:var(--bg); font-size:.85rem; font-weight:700; flex:none; }
  .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top:12px; }
  textarea, input[type=text], select { width:100%; padding:10px 12px; font:inherit; color:inherit; background:var(--bg);
             border:1px solid var(--line); border-radius:10px; }
  textarea { min-height:170px; resize:vertical; line-height:1.5; }
  textarea:focus, input:focus, select:focus { outline:2px solid var(--accent); outline-offset:1px; }
  select { width:auto; max-width:100%; margin-bottom:10px; }
  button { font:inherit; padding:9px 16px; border-radius:10px; border:1px solid var(--line); background:var(--card);
           color:inherit; cursor:pointer; } button:hover { border-color:var(--accent); }
  button.main { background:var(--accent); color:var(--bg); border-color:var(--accent); font-weight:600; padding:10px 22px; }
  .hint { font-size:.88rem; color:var(--muted); margin:10px 0 0; }
  .summary { display:flex; gap:8px; flex-wrap:wrap; margin:14px 0 4px; }
  .chip { padding:4px 12px; border-radius:999px; font-size:.88rem; font-weight:600; }
  .chip.exact { background:var(--ok-bg); color:var(--ok); } .chip.approximate { background:var(--warn-bg); color:var(--warn); }
  .chip.missing { background:var(--ko-bg); color:var(--ko); }
  .verdict { padding:14px 18px; border-radius:12px; font-weight:700; font-size:1.05rem; }
  .verdict.yes { background:var(--ok-bg); color:var(--ok); } .verdict.no { background:var(--ko-bg); color:var(--ko); }
  .item { background:var(--card); border:1px solid var(--line); border-left:6px solid var(--line); border-radius:10px;
          padding:12px 16px; margin-top:10px; }
  .item.exact { border-left-color:var(--ok); } .item.approximate { border-left-color:var(--warn); }
  .item.missing { border-left-color:var(--ko); }
  .tag { font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; }
  .exact .tag { color:var(--ok); } .approximate .tag { color:var(--warn); } .missing .tag { color:var(--ko); }
  .quote { margin-top:2px; }
  .cmp { margin-top:10px; font-size:.93rem; padding-top:8px; border-top:1px dashed var(--line); }
  .cmp small { display:block; color:var(--muted); margin-top:4px; }
  mark { background:var(--ko-bg); color:var(--ko); font-weight:700; border-radius:3px; padding:0 3px; }
  footer { margin-top:28px; font-size:.85rem; color:var(--muted); }
</style></head><body><main>
<header>
  <h1>Vérificateur de citations</h1>
  <p class="sub">Une IA qui répond sur un document peut inventer ou déformer ses citations. Cet outil vérifie que chaque passage cité existe vraiment dans le document.</p>
</header>

<section class="step">
  <h2><span class="n">1</span> Le document</h2>
  <select id="ex" aria-label="Documents d'exemple"><option value="">Charger un document d'exemple...</option></select>
  <textarea id="doc" placeholder="Colle ici le texte du document (contrat, acte, article...)"></textarea>
</section>

<section class="step">
  <h2><span class="n">2</span> Demander à une IA</h2>
  <input type="text" id="q" placeholder="Ta question sur le document">
  <div class="row">
    <button id="askClaude">Demander à Claude</button>
    <button id="askGpt">Demander à ChatGPT</button>
    <button id="copyPrompt">Copier le prompt</button>
  </div>
  <p class="hint" id="askHint">L'IA s'ouvre dans un nouvel onglet avec le prompt déjà rempli. Le document ne part chez elle que si tu cliques ici. Copie ensuite sa réponse.</p>
</section>

<section class="step">
  <h2><span class="n">3</span> La réponse de l'IA</h2>
  <textarea id="ans" placeholder="Colle ici la réponse de l'IA, avec ses citations entre guillemets"></textarea>
  <div class="row"><button class="main" id="go">Vérifier les citations</button></div>
</section>

<div id="out" aria-live="polite"></div>
<footer>L'outil vérifie que les citations existent, pas que la réponse les interprète correctement.<br>
Quand cette page est hébergée en ligne, le texte collé est envoyé au serveur pour être vérifié, sans être enregistré : n'y colle pas de document confidentiel.</footer>
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
  const count = status => report.results.filter(r => r.status === status).length;
  let html = '<div class="verdict ' + (report.sourced ? "yes" : "no") + '">' +
    (report.sourced ? "Réponse sourcée" : "Réponse NON sourcée") + " (score " + report.score + ")</div>" +
    '<div class="summary"><span class="chip exact">' + count("exact") + " exacte(s)</span>" +
    '<span class="chip approximate">' + count("approximate") + " à relire</span>" +
    '<span class="chip missing">' + count("missing") + " introuvable(s)</span></div>";
  for (const r of report.results) {
    html += '<div class="item ' + r.status + '"><span class="tag">' + LABEL[r.status] +
      " - ressemblance " + r.similarity.toFixed(2) + '</span><div class="quote">' + esc(r.citation) + "</div>";
    if (r.status === "missing") {
      html += '<div class="cmp"><small>Aucune phrase comparable dans le document.</small></div>';
    } else if (r.status === "approximate") {
      html += '<div class="cmp"><small>Citation de l\'IA</small>' + words(r.diff_citation) +
        "<small>Phrase la plus proche dans le document</small>" + words(r.diff_passage) + "</div>";
    }
    html += "</div>";
  }
  $("out").innerHTML = html;
  $("out").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

$("go").onclick = async () => {
  if (!$("doc").value.trim()) { $("out").innerHTML = '<div class="verdict no">Colle d\'abord un document (étape 1).</div>'; return; }
  const citations = extractQuotes($("ans").value);
  if (!citations.length) {
    $("out").innerHTML = '<div class="verdict no">Aucune citation entre guillemets dans la réponse : elle n\'est donc pas sourcée.</div>';
    return;
  }
  const res = await fetch("/verify", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document: $("doc").value, citations }) });
  const report = await res.json();
  if (report.error) { $("out").innerHTML = '<div class="verdict no">' + esc(report.error) + "</div>"; return; }
  render(report);
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
  if (!$("doc").value.trim()) { $("askHint").textContent = "Colle d'abord un document (étape 1)."; return; }
  const prompt = buildPrompt(), url = base + encodeURIComponent(prompt);
  if (url.length <= MAX_URL) {
    window.open(url, "_blank", "noopener");
    $("askHint").textContent = "L'IA s'est ouverte dans un nouvel onglet. Copie sa réponse et colle-la à l'étape 3.";
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
  $("askHint").textContent = (await copyText(buildPrompt())) ? "Prompt copié. Colle-le dans l'IA de ton choix." : "Copie impossible : sélectionne le texte à la main.";
};

let EXAMPLES = [];
function loadExample(i) {
  const e = EXAMPLES[i];
  if (!e) return;
  $("doc").value = e.document; $("q").value = e.question; $("ans").value = ""; $("out").innerHTML = "";
}
fetch("/examples").then(r => r.json()).then(list => {
  EXAMPLES = list;
  list.forEach((e, i) => { const o = document.createElement("option"); o.value = i; o.textContent = e.name; $("ex").appendChild(o); });
  if (!$("doc").value && list.length) { $("ex").value = 0; loadExample(0); }
});
$("ex").onchange = () => loadExample($("ex").value);
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
            if size > MAX_BODY_BYTES:
                raise ValueError("Requête trop volumineuse.")
            payload = json.loads(self.rfile.read(size))
            document = str(payload.get("document", ""))
            citations = [str(c) for c in payload.get("citations", [])]
            validate(document, citations)
            report = analyse(document, citations)
        except json.JSONDecodeError:
            return self._send(json.dumps({"error": "requête invalide"}), "application/json", 400)
        except ValueError as error:  # entrée trop grosse : le message est fait pour être affiché
            return self._send(json.dumps({"error": str(error)}), "application/json", 400)
        except (TypeError, AttributeError):
            return self._send(json.dumps({"error": "requête invalide"}), "application/json", 400)
        self._send(json.dumps(report), "application/json")

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Interface disponible sur {url} (Ctrl+C pour arrêter)")
    if HOST in ("127.0.0.1", "localhost"):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêté.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
