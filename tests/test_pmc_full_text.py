import unittest
import xml.etree.ElementTree as ET

from agnostik.pmc_full_text import REFERENCES_OMITTED_NOTE, render_article_text


SAMPLE_ARTICLE = """<article>
<front><journal-meta><journal-title>Test Journal</journal-title></journal-meta>
<article-meta><article-id pub-id-type="pmcid">PMC123</article-id>
<title-group><article-title>EGFR therapy study</article-title></title-group>
<contrib-group><contrib contrib-type="author"><name><surname>Doe</surname><given-names>Jane</given-names></name></contrib></contrib-group>
<abstract><p>Complete abstract text.</p></abstract></article-meta></front>
<body><sec><title>Results</title><p>Full body with <bold>important</bold> evidence.</p></sec></body>
<back><ref-list><ref><mixed-citation>Reference one.</mixed-citation></ref></ref-list></back>
</article>"""


class RenderArticleTextTests(unittest.TestCase):
    def test_renders_clean_parseltongue_source(self):
        article = ET.fromstring(SAMPLE_ARTICLE)
        text = render_article_text(article, "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/")
        self.assertIn("# EGFR therapy study", text)
        self.assertIn("## Full article", text)
        self.assertIn("Full body with important evidence.", text)
        self.assertNotIn("<strong>", text)

    def test_renders_abstract_and_metadata_for_reading(self):
        article = ET.fromstring(SAMPLE_ARTICLE)
        text = render_article_text(article, "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/")
        self.assertIn("Complete abstract text.", text)
        self.assertIn("PMCID: PMC123", text)

    def test_reference_list_is_left_out_and_the_omission_is_marked(self):
        article = ET.fromstring(SAMPLE_ARTICLE)
        text = render_article_text(article, "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/")
        self.assertNotIn("Reference one.", text)
        self.assertNotIn("## References", text)
        self.assertTrue(text.rstrip().endswith(REFERENCES_OMITTED_NOTE))

    def test_no_omission_note_when_the_article_has_no_reference_list(self):
        article = ET.fromstring(SAMPLE_ARTICLE.replace("<ref-list><ref><mixed-citation>Reference one.</mixed-citation></ref></ref-list>", ""))
        text = render_article_text(article, "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/")
        self.assertNotIn(REFERENCES_OMITTED_NOTE, text)


if __name__ == "__main__":
    unittest.main()
