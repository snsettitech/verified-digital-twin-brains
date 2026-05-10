from pathlib import Path
import unittest


MAIN_PY = Path(__file__).resolve().parents[1] / "main.py"


class MainFeatureFlagCleanupTests(unittest.TestCase):
    def test_main_omits_stale_vc_routes_flag_plumbing(self):
        source = MAIN_PY.read_text()

        self.assertIn("ENABLE_REALTIME_INGESTION", source)
        self.assertIn("ENABLE_ENHANCED_INGESTION", source)
        self.assertIn("ENABLE_ADVISOR_RETRIEVAL", source)
        self.assertIn("DEEP_RESEARCH_ENABLED", source)
        self.assertIn("app.include_router(specializations.router)", source)
        self.assertNotIn("ENABLE_VC_ROUTES", source)
        self.assertNotIn("VC_ROUTES_ENABLED", source)
        self.assertNotIn("vc_routes", source)
        self.assertNotIn("VC Routes:", source)


if __name__ == "__main__":
    unittest.main()
