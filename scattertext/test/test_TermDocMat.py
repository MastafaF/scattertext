import os
import pkgutil
from unittest import TestCase

import numpy as np
import pandas as pd

from scattertext.termscoring.ScaledFScore import InvalidScalerException
from scattertext import TermDocMatrixFromPandas
from scattertext.FastButCrapNLP import fast_but_crap_nlp
from scattertext.TermDocMatrix import TermDocMatrix
from scattertext.TermDocMatrixFactory import build_from_category_whitespace_delimited_text
from scattertext.test.test_corpusFromPandas import get_docs_categories


def make_a_test_term_doc_matrix():
	# type: () -> TermDocMatrix
	return build_from_category_whitespace_delimited_text(
		get_test_categories_and_documents()
	)


def get_test_categories_and_documents():
	return [
		['a', '''hello my name is joe.
			i've got a wife and three kids and i'm working.
			in a button factory'''],
		['b', '''this is another type of document
			 another sentence in another document
			 my name isn't joe here.'''],
		['b', '''this is another document.
				blah blah blah''']
	]


class TestTermDocMat(TestCase):
	@classmethod
	def setUp(cls):
		cls.tdm = make_a_test_term_doc_matrix()

	def test_get_term_freq_df(self):
		df = self.tdm.get_term_freq_df().sort_values('b freq', ascending=False)[:3]
		self.assertEqual(list(df.index), ['another', 'blah', 'blah blah'])
		self.assertEqual(list(df['a freq']), [0, 0, 0])
		self.assertEqual(list(df['b freq']), [4, 3, 2])
		self.assertEqual(list(self.tdm.get_term_freq_df()
		                      .sort_values('a freq', ascending=False)
		                      [:3]['a freq']),
		                 [2, 2, 1])

	def test_total_unigram_count(self):
		self.assertEqual(self.tdm.get_total_unigram_count(), 36)

	def test_get_term_df(self):
		categories, documents = get_docs_categories()
		df = pd.DataFrame({'category': categories,
		                   'text': documents})
		tdm_factory = TermDocMatrixFromPandas(df,
		                                      'category',
		                                      'text',
		                                      nlp=fast_but_crap_nlp)
		term_doc_matrix = tdm_factory.build()

		term_df = term_doc_matrix.get_term_freq_df()
		self.assertEqual(dict(term_df.ix['speak up']),
		                 {'??? freq': 2, 'hamlet freq': 0, 'jay-z/r. kelly freq': 1})
		self.assertEqual(dict(term_df.ix['that']),
		                 {'??? freq': 0, 'hamlet freq': 2, 'jay-z/r. kelly freq': 0})

	def test_term_doc_lists(self):
		term_doc_lists = self.tdm.term_doc_lists()
		self.assertEqual(type(term_doc_lists), dict)
		self.assertEqual(term_doc_lists['this'], [1, 2])
		self.assertEqual(term_doc_lists['another document'], [1])
		self.assertEqual(term_doc_lists['is'], [0, 1, 2])

	def test_remove_terms(self):
		tdm = make_a_test_term_doc_matrix()
		with self.assertRaises(KeyError):
			tdm.remove_terms(['elephant'])
		tdm_removed = tdm.remove_terms(['hello', 'this', 'is'])
		removed_df = tdm_removed.get_term_freq_df()
		df = tdm.get_term_freq_df()
		self.assertEqual(tdm_removed.get_num_docs(), tdm.get_num_docs())
		self.assertEqual(len(removed_df), len(df) - 3)
		self.assertNotIn('hello', removed_df.index)
		self.assertIn('hello', df.index)

	def test_term_scores(self):
		df = self.tdm.get_term_freq_df()
		df['posterior ratio'] = self.tdm.get_posterior_mean_ratio_scores('b')
		scores = self.tdm.get_scaled_f_scores('b', scaler_algo='percentile')
		df['scaled_f_score'] = np.array(scores)
		with self.assertRaises(InvalidScalerException):
			self.tdm.get_scaled_f_scores('a', scaler_algo='x')
		self.tdm.get_scaled_f_scores('a', scaler_algo='percentile')
		self.tdm.get_scaled_f_scores('a', scaler_algo='normcdf')
		df['rudder'] = self.tdm.get_rudder_scores('b')
		df['fisher oddsratio'], df['fisher pval'] = self.tdm.get_fisher_scores('b')

		self.assertEqual(list(df.sort_values(by='posterior ratio', ascending=False).index[:3]),
		                 ['another', 'blah', 'blah blah'])
		self.assertEqual(list(df.sort_values(by='scaled_f_score', ascending=False).index[:3]),
		                 ['another', 'blah', 'blah blah'])

		# to do: come up with faster way of testing fisher
		# self.assertEqual(list(df.sort_values(by='fisher pval', ascending=True).index[:3]),
		#                 ['another', 'blah', 'blah blah'])

		self.assertEqual(list(df.sort_values(by='rudder', ascending=True).index[:3]),
		                 ['another', 'blah', 'blah blah'])

	def test_term_scores_background(self):
		hamlet = get_hamlet_term_doc_matrix()
		df = hamlet.get_scaled_f_score_scores_vs_background(
			scaler_algo='none'
		)
		self.assertEqual({u'corpus', u'background', u'Scaled f-score'},
		                 set(df.columns))
		self.assertEqual(list(df.index[:3]),
		                 ['polonius', 'laertes', 'osric'])

		df = hamlet.get_rudder_scores_vs_background()
		self.assertEqual({u'corpus', u'background', u'Rudder'},
		                 set(df.columns))
		self.assertEqual(list(df.index[:3]),
		                 ['voltimand', 'knavish', 'mobled'])

		df = hamlet.get_posterior_mean_ratio_scores_vs_background()
		self.assertEqual({u'corpus', u'background', u'Log Posterior Mean Ratio'},
		                 set(df.columns))
		self.assertEqual(list(df.index[:3]),
		                 ['hamlet', 'horatio', 'claudius'])

	# to do: come up with faster way of testing fisher
	# df = hamlet.get_fisher_scores_vs_background()
	# self.assertEqual(list(df.sort_values(by='Bonferroni-corrected p-values', ascending=True).index[:3]),
	#                 ['voltimand', 'knavish', 'mobled'])

	def test_log_reg(self):
		hamlet = get_hamlet_term_doc_matrix()
		df = hamlet.get_term_freq_df()
		df['logreg'], acc, baseline = hamlet.get_logistic_regression_coefs_l2('hamlet')
		l1scores, acc, baseline = hamlet.get_logistic_regression_coefs_l1('hamlet')
		self.assertGreaterEqual(acc, 0)
		self.assertGreaterEqual(baseline, 0)
		self.assertGreaterEqual(1, acc)
		self.assertGreaterEqual(1, baseline)
		self.assertEqual(list(df.sort_values(by='logreg', ascending=False).index[:3]),
		                 ['hamlet', 'hamlet,', 'the'])




def get_hamlet_term_doc_matrix():
	# type: () -> TermDocMatrix
	hamlet_docs = get_hamlet_docs()

	hamlet_term_doc_matrix = build_from_category_whitespace_delimited_text(
		[(get_hamlet_snippet_binary_category(text), text)
		 for i, text in enumerate(hamlet_docs)]
	)
	return hamlet_term_doc_matrix


def get_hamlet_snippet_binary_category(text):
	return 'hamlet' if 'hamlet' in text.lower() else 'not hamlet'


def get_hamlet_docs():
	try:
		cwd = os.path.dirname(os.path.abspath(__file__))
		path = os.path.join(cwd, '..', 'data', 'hamlet.txt')
		buf = open(path).read()
	except:
		buf = pkgutil.get_data('scattertext', os.path.join('data', 'hamlet.txt'))
	hamlet_docs = buf.split('\n\n')
	return hamlet_docs
