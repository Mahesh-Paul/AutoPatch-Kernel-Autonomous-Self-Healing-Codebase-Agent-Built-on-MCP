"""Phase 5 Verification Tests: Live 'Flight Deck' Web Dashboard & CLI Runner.

Validates that:
1. FastAPI dashboard root (/) serves cyber-systems dark mode HTML with 200 OK.
2. /api/status returns live Meta model matrix, AST focal node, and Z3 certificate.
3. /api/voice-trigger simulates Meta Muse Voice Transcribe incident dispatch.
4. /api/sam-visual-mask returns Meta SAM 3.1 visual segmentation coordinates.
5. main.py CLI arguments (--demo, --ui, --voice) parse deterministically.
"""
import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from dashboard.app import (
    get_dashboard_ui,
    get_system_status,
    voice_transcribe_trigger,
    get_sam31_visual_mask,
    VoiceTriggerRequest,
)
from main import get_cli_parser


class TestPhase5DashboardAndCLI(unittest.TestCase):

    def test_01_dashboard_root_html_renders(self):
        """Verifies root endpoint serves 200 OK with cyber-systems HTML."""
        response = get_dashboard_ui()
        self.assertEqual(response.status_code, 200)
        content = response.body.decode("utf-8")
        self.assertIn("AutoPatch-Kernel Flight Deck", content)
        self.assertIn("Muse Spark 1.3", content)
        self.assertIn("SAM 3.1", content)
        self.assertIn("Muse Voice", content)
        self.assertIn("Cryptographic Z3 SMT Verification Certificate", content)

    def test_02_api_status_endpoint(self):
        """Verifies /api/status returns active state of all Meta models and SMT proofs."""
        data = get_system_status()
        self.assertEqual(data["status"], "ONLINE")
        self.assertIn("meta_model_matrix", data)
        self.assertEqual(data["meta_model_matrix"]["muse_spark_1_3"]["status"], "ACTIVE")
        self.assertEqual(data["meta_model_matrix"]["sam_3_1"]["status"], "READY")
        self.assertTrue(data["z3_verified"])
        self.assertIn("calculate_discount", data["ast_focal_node"]["name"])

    def test_03_voice_trigger_endpoint(self):
        """Verifies /api/voice-trigger accepts audio transcript and returns dispatch status."""
        req = VoiceTriggerRequest(
            audio_transcript_input="AutoPatch, trigger autonomous repair for payment processor.",
            operator_id="test-engineer-01",
        )
        data = voice_transcribe_trigger(req)
        self.assertEqual(data["action_dispatched"], "AUTONOMOUS_HEAL_TOURNAMENT")
        self.assertIn("Meta Muse Voice Transcribe", data["voice_engine"])
        self.assertEqual(data["status"], "DISPATCHED")
        self.assertEqual(data["operator_id"], "test-engineer-01")

    def test_04_sam31_visual_mask_endpoint(self):
        """Verifies /api/sam-visual-mask returns SAM 3.1 visual crash segmentation data."""
        data = get_sam31_visual_mask()
        self.assertEqual(data["model"], "Meta-SAM-3.1")
        self.assertEqual(data["failing_component"], "PaymentCheckoutForm.DiscountInput")
        self.assertGreater(data["confidence_score"], 0.95)
        self.assertIn("polygon_points", data)

    def test_05_main_cli_help_and_parsing(self):
        """Verifies main.py CLI arguments parse cleanly."""
        parser = get_cli_parser()
        args = parser.parse_args(["--demo"])
        self.assertTrue(args.demo)
        self.assertFalse(args.ui)

        args_ui = parser.parse_args(["--ui", "--port", "9000"])
        self.assertTrue(args_ui.ui)
        self.assertEqual(args_ui.port, 9000)

        args_voice = parser.parse_args(["--voice", "Heal payment crash"])
        self.assertEqual(args_voice.voice, "Heal payment crash")


if __name__ == "__main__":
    unittest.main()
