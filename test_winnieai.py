import json
import math
from pathlib import Path
import tempfile
import unittest
from winnieai import Brain

class LearningTests(unittest.TestCase):
    def test_window_and_counts(self):
        b=Brain(False);b.learn('apples trees fruit. Pears trees fruit.')
        self.assertEqual(b.count,2);self.assertEqual(b.df['trees'],2)
        self.assertEqual(b.graph['apples']['trees'],1)
        self.assertEqual(b.graph['trees']['apples'],1)
        self.assertTrue(any(t=='pears' for t,s in b.search('apples')))
        self.assertAlmostEqual(sum(v*v for v in b.vectors['apples'].values()),1)
    def test_single_word(self):
        b=Brain(False);b.learn('zebra');self.assertIn('zebra',b.graph)
    def test_answer_and_correction(self):
        b=Brain(False);b.teach('favorite color','Blue.');self.assertEqual(b.answer('favorite color')[0],'Blue.')
        b.teach('favorite color','Green.');self.assertEqual(b.answer('favorite color')[0],'Green.');self.assertEqual(len(b.qa),1)
    def test_sentence_retrieval(self):
        b=Brain(False);b.learn('Apples grow on trees.');self.assertIn('Apples grow on trees.',b.answer('where apples grow')[0])
        self.assertIn("don't know",b.answer('quantum elephants')[0])
    def test_roundtrip(self):
        b=Brain(False);b.learn('Apples and pears are fruit.');b.teach('capital France','Paris.')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.Winnieai';b.save(p);c=Brain(False);c.load(p)
            self.assertEqual(b.data(),c.data());self.assertEqual(b.search('fruit'),c.search('fruit'))
            self.assertEqual(c.answer('capital France')[0],'Paris.')
            self.assertEqual(p.stat().st_mode & 0o777,0o600)
    def test_legacy(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'old.Winnieai';p.write_text(json.dumps({'hello':{'hi':5},'hi':{'hello':5}}))
            b=Brain(False);b.load(p);self.assertEqual(b.graph['hello']['hi'],5)
    def test_bad_import_never_erases(self):
        b=Brain();before=b.data()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json'
            for value in [[],{'hello':{'hi':-1}}, {'hello':{'hi':float('nan')}}, {'format':'WinnieAI','version':999}, {'hello':[]}]:
                p.write_text(json.dumps(value))
                with self.assertRaises(ValueError):b.load(p)
                self.assertEqual(b.data(),before)
    def test_empty(self):
        with self.assertRaises(ValueError):Brain(False).learn(' ')
    def test_limits(self):
        with self.assertRaises(ValueError):Brain(False).learn('x'*100001)
    def test_unicode(self):
        b=Brain(False);b.learn('café café thé');self.assertIn('café',b.graph)

if __name__=='__main__':unittest.main()
