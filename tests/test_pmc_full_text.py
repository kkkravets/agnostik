import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from agnostik.pmc_full_text import render_article_html, render_article_text


SAMPLE_ARTICLE = """<article>
<front><journal-meta><journal-title>Test Journal</journal-title></journal-meta>
<article-meta><article-id pub-id-type="pmcid">PMC123</article-id>
<title-group><article-title>EGFR therapy study</article-title></title-group>
<contrib-group><contrib contrib-type="author"><name><surname>Doe</surname><given-names>Jane</given-names></name></contrib></contrib-group>
<abstract><p>Complete abstract text.</p></abstract></article-meta></front>
<body><sec><title>Results</title><p>Full body with <bold>important</bold> evidence.</p></sec></body>
<back><ref-list><ref><mixed-citation>Reference one.</mixed-citation></ref></ref-list></back>
</article>"""


class RenderArticleHtmlTests(unittest.TestCase):
    def test_renders_abstract_body_and_references(self):
        article = ET.fromstring(SAMPLE_ARTICLE)
        html = render_article_html(article, "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/")
        self.assertIn("Complete abstract text.", html)
        self.assertIn("Full body with <strong>important</strong> evidence.", html)
        self.assertIn("Reference one.", html)
        self.assertIn("EGFR therapy study", html)

    def test_renders_clean_parseltongue_source(self):
        article = ET.fromstring(SAMPLE_ARTICLE)
        text = render_article_text(article, "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/")
        self.assertIn("# EGFR therapy study", text)
        self.assertIn("## Full article", text)
        self.assertIn("Full body with important evidence.", text)
        self.assertNotIn("<strong>", text)


if __name__ == "__main__":
    unittest.main()
