import sys
import unittest
from pathlib import Path

# Add parent directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Test pipeline essentials
from planner.contracts import Article, validate_article, final_status
from planner.security import public_url, validate_upload, redact
from planner.review import units_for
from planner.sample import sample_result
from planner.exports import download_markdown, make_pdf

class TestPlannerApp(unittest.TestCase):
    def test_sample_loading(self):
        sample = sample_result()
        self.assertIn("brief", sample)
        self.assertIn("outline", sample["brief"])
        self.assertGreater(len(sample["brief"]["outline"]), 0)
        self.assertIn(sample["status"], ("automated_review_passed", "draft_without_sources"))

    def test_exports_markdown_and_pdf(self):
        sample = sample_result()
        md = download_markdown(sample)
        self.assertIn("Machine Learning", md)
        pdf = make_pdf(sample)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_security_validation(self):
        self.assertEqual(validate_upload("test.txt", b"hello text"), ".txt")
        self.assertEqual(validate_upload("test.pdf", b"%PDF-1.4 valid"), ".pdf")
        with self.assertRaises(ValueError):
            validate_upload("script.exe", b"malware")

    def test_redact(self):
        secret = "gsk_1234567890abcdef"
        redacted = redact(f"Key is {secret}")
        self.assertNotIn(secret, redacted)

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPlannerApp)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("ALL TESTS PASSED SUCCESSFULLY!")
