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
        if r["status"] != "exact":
            passage, _ = closest_sentence(document, r["citation"])
            left, right = diff_words(r["citation"], passage)
            r["passage"] = passage
            r["diff_citation"] = left
            r["diff_passage"] = right
    return report


def load_example():
    document = (HERE / "examples" / "acte_vente.txt").read_text(encoding="utf-8")
    answer = json.loads((HERE / "examples" / "reponse_inventee.json").read_text(encoding="utf-8"))
    return {"document": document, "citations": "\n".join(answer["citations"])}


PAGE = """<!doctype html>
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
  textarea { width:100%; min-height:220px; padding:10px; font:inherit; color:inherit; background:var(--card);
             border:1px solid var(--line); border-radius:8px; resize:vertical; }
  .actions { margin:16px 0; display:flex; gap:10px; flex-wrap:wrap; }
  button { font:inherit; padding:8px 16px; border-radius:8px; border:1px solid var(--line); background:var(--card);
           color:inherit; cursor:pointer; } button.main { background:var(--fg); color:var(--bg); border-color:var(--fg); }
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
<p class="sub">Colle un document et les citations d'une réponse d'IA (une par ligne). L'outil vérifie que chaque citation existe vraiment dans le document.</p>
<div class="cols">
  <div><label for="doc">Document source</label><textarea id="doc"></textarea></div>
  <div><label for="cit">Citations de la réponse (une par ligne)</label><textarea id="cit"></textarea></div>
</div>
<div class="actions"><button class="main" id="go">Vérifier</button><button id="ex">Charger l'exemple</button></div>
<div id="out" aria-live="polite"></div>
<footer>L'outil vérifie que les citations existent, pas que la réponse les interprète correctement. Tout reste sur ton ordinateur.</footer>
</main>
<script>
const $ = id => document.getElementById(id);
const LABEL = { exact: "Exacte", approximate: "À relire", missing: "Introuvable" };
const esc = s => s.replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const words = pairs => pairs.map(([w, changed]) => changed ? "<mark>" + esc(w) + "</mark>" : esc(w)).join(" ");

function render(report) {
  let html = '<div class="verdict ' + (report.sourced ? "yes" : "no") + '">' +
    (report.sourced ? "Réponse sourcée" : "Réponse NON sourcée") + " - score " + report.score + "</div>";
  for (const r of report.results) {
    html += '<div class="item ' + r.status + '"><span class="tag">' + LABEL[r.status] +
      " (" + r.similarity.toFixed(2) + ")</span><div>" + esc(r.citation) + "</div>";
    if (r.status !== "exact") {
      html += '<div class="cmp"><small>Citation</small>' + words(r.diff_citation) +
        "<small>Phrase la plus proche du document</small>" + words(r.diff_passage) + "</div>";
    }
    html += "</div>";
  }
  $("out").innerHTML = html;
}

$("go").onclick = async () => {
  const citations = $("cit").value.split("\\n").map(s => s.trim()).filter(Boolean);
  const res = await fetch("/verify", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document: $("doc").value, citations }) });
  render(await res.json());
};
$("ex").onclick = async () => {
  const ex = await (await fetch("/example")).json();
  $("doc").value = ex.document; $("cit").value = ex.citations; $("go").click();
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
        elif self.path == "/example":
            self._send(json.dumps(load_example()), "application/json")
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
