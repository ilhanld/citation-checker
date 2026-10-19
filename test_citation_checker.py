import json
import os
import unittest

from citation_checker import (check_citation, main, normalize, score, verify_answer,
                              verify_citations)

DOC = """Acte de vente du 12 mars 2019.
Le vendeur déclare que le bien est libre de toute  hypothèque.
L’acquéreur s'engage à payer le prix de 250 000 euros – frais inclus.
Une servitude de passage grève la parcelle."""


class TestNormalize(unittest.TestCase):
    def test_minuscules_et_accents(self):
        self.assertEqual(normalize("Déclaré À L'ÉCOLE"), "declare a l'ecole")

    def test_apostrophes_et_tirets(self):
        self.assertEqual(normalize("L’acquéreur ʼ ‘x a – b — c"), "l'acquereur ' 'x a - b - c")

    def test_espaces(self):
        self.assertEqual(normalize("  un \t deux\n\ntrois  "), "un deux trois")


class TestCheckCitation(unittest.TestCase):
    def test_exacte(self):
        self.assertEqual(check_citation(DOC, "Une servitude de passage grève la parcelle.")["status"], "exact")

    def test_insensible_casse_accents_espaces(self):
        self.assertEqual(check_citation(DOC, "LE VENDEUR DECLARE que le bien est libre de toute hypotheque")["status"], "exact")

    def test_apostrophe_typographique_et_tiret(self):
        c = "L'acquéreur s’engage à payer le prix de 250 000 euros - frais inclus"
        self.assertEqual(check_citation(DOC, c)["status"], "exact")

    def test_presque_exacte_est_a_relire(self):
        c = "Le vendeur declare que le bien est libre de toute hypotheques"
        r = check_citation(DOC, c)
        self.assertEqual(r["status"], "approximate")
        self.assertGreaterEqual(r["similarity"], 0.9)

    def test_chiffre_change_n_est_pas_exact(self):
        r = check_citation(DOC, "payer le prix de 350 000 euros - frais inclus")
        self.assertNotEqual(r["status"], "exact")

    def test_inventee(self):
        r = check_citation(DOC, "Le bien est vendu sans servitude ni hypothèque et avec un jardin")
        self.assertEqual(r["status"], "missing")

    def test_vide(self):
        self.assertEqual(check_citation(DOC, "   ")["status"], "missing")


class TestVerifyCitationsEtScore(unittest.TestCase):
    def test_ordre_et_texte_d_origine(self):
        cites = ["Servitude DE passage", "phrase inventée", "acte de vente du 12 mars 2019"]
        r = verify_citations(DOC, cites)
        self.assertEqual(r["found"], ["Servitude DE passage", "acte de vente du 12 mars 2019"])
        self.assertEqual(r["missing"], ["phrase inventée"])

    def test_score(self):
        self.assertEqual(score(DOC, ["servitude de passage", "libre de toute hypotheque", "250 000 euros", "inventé"]), 0.75)
        self.assertEqual(score(DOC, ["servitude de passage", "inventé un", "inventé deux"]), 0.33)

    def test_score_sans_citation(self):
        self.assertEqual(score(DOC, []), 0.0)


class TestVerifyAnswer(unittest.TestCase):
    def test_sourcee(self):
        a = {"text": "…", "citations": ["Une servitude de passage grève la parcelle"]}
        r = verify_answer(DOC, a)
        self.assertTrue(r["sourced"])
        self.assertEqual((r["score"], r["missing"], r["approximate"]), (1.0, [], []))

    def test_une_citation_inventee(self):
        a = {"text": "…", "citations": ["servitude de passage", "bail commercial en cours depuis dix ans"]}
        r = verify_answer(DOC, a)
        self.assertFalse(r["sourced"])
        self.assertEqual(r["score"], 0.5)
        self.assertEqual(r["missing"], ["bail commercial en cours depuis dix ans"])

    def test_aucune_citation_n_est_pas_sourcee(self):
        r = verify_answer(DOC, {"text": "Réponse sans source", "citations": []})
        self.assertFalse(r["sourced"])
        self.assertEqual(r["score"], 0.0)

    def test_presque_exacte_ne_suffit_pas(self):
        a = {"text": "…", "citations": ["Le vendeur declare que le bien est libre de toute hypotheques"]}
        r = verify_answer(DOC, a)
        self.assertFalse(r["sourced"])
        self.assertEqual(len(r["approximate"]), 1)


class TestCommandeEtExemples(unittest.TestCase):
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")

    def test_exemple_ok(self):
        code = main([os.path.join(self.base, "acte_vente.txt"), os.path.join(self.base, "reponse_ok.json")])
        self.assertEqual(code, 0)

    def test_exemple_inventee(self):
        code = main([os.path.join(self.base, "acte_vente.txt"), os.path.join(self.base, "reponse_inventee.json")])
        self.assertEqual(code, 1)

    def test_exemples_json_valides(self):
        for name in ("reponse_ok.json", "reponse_inventee.json"):
            with open(os.path.join(self.base, name), encoding="utf-8") as f:
                self.assertIn("citations", json.load(f))


if __name__ == "__main__":
    unittest.main()
