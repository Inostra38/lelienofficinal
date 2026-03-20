from django.test import TestCase
from .utils import sanitize_quill_html


class SanitizeQuillHtmlTest(TestCase):

    def test_strips_script_tag(self):
        # bleach supprime la balise <script> mais conserve le texte brut (non exécutable)
        dirty = "<p>Bonjour</p><script>alert('xss')</script>"
        result = sanitize_quill_html(dirty)
        self.assertNotIn('<script>', result)
        self.assertNotIn('</script>', result)
        self.assertIn('<p>Bonjour</p>', result)

    def test_strips_on_event_attributes(self):
        dirty = '<p onclick="evil()">Texte</p>'
        result = sanitize_quill_html(dirty)
        self.assertNotIn('onclick', result)
        self.assertIn('Texte', result)

    def test_preserves_allowed_tags(self):
        clean = '<p><strong>Titre</strong></p><ul><li>Item</li></ul>'
        result = sanitize_quill_html(clean)
        self.assertIn('<strong>Titre</strong>', result)
        self.assertIn('<li>Item</li>', result)

    def test_returns_empty_string_for_none(self):
        self.assertEqual(sanitize_quill_html(None), '')

    def test_returns_empty_string_for_empty(self):
        self.assertEqual(sanitize_quill_html(''), '')
