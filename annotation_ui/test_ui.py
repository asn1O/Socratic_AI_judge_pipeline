"""test_ui.py - Comprehensive automated tests for Annotation UI data loader, Excel manager, and REST API."""

import json
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from annotation_ui.data_loader import AnnotationDataLoader, SAMPLES_META
from annotation_ui.excel_manager import ExcelAnnotationManager, METRIC_COLUMNS
from annotation_ui.app import AnnotationRequestHandler


class TestDataLoader(unittest.TestCase):
    """Test data loading and indexing."""

    @classmethod
    def setUpClass(cls):
        cls.base_dir = Path(__file__).resolve().parent.parent
        cls.loader = AnnotationDataLoader(cls.base_dir)

    def test_samples_loaded(self):
        keys = self.loader.get_sample_keys()
        self.assertEqual(set(keys), {"random_sample", "metric_profile_sample", "judge_disagreement_sample"})

        # Check counts
        self.assertEqual(len(self.loader.get_id_list("random_sample")), 240)
        self.assertEqual(len(self.loader.get_id_list("metric_profile_sample")), 120)
        self.assertEqual(len(self.loader.get_id_list("judge_disagreement_sample")), 40)

    def test_first_and_last_ids(self):
        rnd_ids = self.loader.get_id_list("random_sample")
        self.assertEqual(rnd_ids[0], "RND-0001")
        self.assertEqual(rnd_ids[-1], "RND-0240")

        mp_ids = self.loader.get_id_list("metric_profile_sample")
        self.assertEqual(mp_ids[0], "MP-0001")
        self.assertEqual(mp_ids[-1], "MP-0120")

        jd_ids = self.loader.get_id_list("judge_disagreement_sample")
        self.assertEqual(jd_ids[0], "JD-0001")
        self.assertEqual(jd_ids[-1], "JD-0040")

    def test_navigation_pointers(self):
        # First item
        data_first = self.loader.get_conversation_by_id("random_sample", "RND-0001")
        self.assertIsNotNone(data_first)
        self.assertIsNone(data_first["prev_id"])
        self.assertEqual(data_first["next_id"], "RND-0002")
        self.assertEqual(data_first["index"], 1)

        # Second item
        data_second = self.loader.get_conversation_by_id("random_sample", "RND-0002")
        self.assertEqual(data_second["prev_id"], "RND-0001")
        self.assertEqual(data_second["next_id"], "RND-0003")
        self.assertEqual(data_second["index"], 2)

        # Last item
        data_last = self.loader.get_conversation_by_id("random_sample", "RND-0240")
        self.assertEqual(data_last["prev_id"], "RND-0239")
        self.assertIsNone(data_last["next_id"])
        self.assertEqual(data_last["index"], 240)

    def test_conversation_content(self):
        data = self.loader.get_conversation_by_id("random_sample", "RND-0001")
        rec = data["record"]
        self.assertIn("conversation", rec)
        conv = rec["conversation"]
        self.assertIn("problem", conv)
        self.assertIn("conversation", conv)
        self.assertGreater(len(conv["conversation"]), 0)

        # Source relative path & index metadata
        self.assertIn("source", rec)
        self.assertIn("relative_path", rec["source"])
        self.assertIn("index", rec["source"])
        self.assertTrue(rec["source"]["relative_path"].endswith(".json"))
        self.assertIsInstance(rec["source"]["index"], int)


class TestExcelManager(unittest.TestCase):
    """Test Excel read/write without altering project production Excel files."""

    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.orig_excel_dir = self.base_dir / "misc" / "annotation_excel_files"
        self.temp_dir = tempfile.mkdtemp()
        self.temp_excel_dir = Path(self.temp_dir)

        # Copy original excel files to temp directory
        for f in self.orig_excel_dir.glob("*.xlsx"):
            shutil.copy(f, self.temp_excel_dir / f.name)

        self.mgr = ExcelAnnotationManager(self.temp_excel_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_initial_status_empty(self):
        status = self.mgr.get_all_status("judge_disagreement_sample")
        self.assertEqual(len(status), 40)
        self.assertTrue(all(not is_graded for is_graded in status.values()))

    def test_save_and_retrieve_scores(self):
        test_scores = {
            "socratic_guidance": 3,
            "scaffolding": 2,
            "state_adaptation": 3,
            "diagnosis": 2,
            "student_agency": 3,
            "progression": 3,
            "coherence": 3,
            "correctness": True,
            "overall_score_out_of_5": 4.5,
            "overall_score_out_of_10": 9.0,
        }

        success, msg = self.mgr.save_scores("judge_disagreement_sample", "JD-0001", test_scores)
        self.assertTrue(success, msg)

        # Check retrieval
        read_scores = self.mgr.get_scores("judge_disagreement_sample", "JD-0001")
        self.assertIsNotNone(read_scores)
        self.assertEqual(read_scores["socratic_guidance"], 3)
        self.assertEqual(read_scores["scaffolding"], 2)
        self.assertEqual(read_scores["correctness"], True)
        self.assertEqual(read_scores["overall_score_out_of_5"], 4.5)
        self.assertEqual(read_scores["overall_score_out_of_10"], 9.0)

        # Verify status update
        status = self.mgr.get_all_status("judge_disagreement_sample")
        self.assertTrue(status["JD-0001"])
        self.assertFalse(status["JD-0002"])

        # Check summary
        summary = self.mgr.get_sample_summary("judge_disagreement_sample")
        self.assertEqual(summary["graded"], 1)
        self.assertEqual(summary["pending"], 39)

    def test_overwrite_scores(self):
        # 1. Initial save
        initial_scores = {"socratic_guidance": 1, "scaffolding": 1, "correctness": False}
        success, _ = self.mgr.save_scores("judge_disagreement_sample", "JD-0001", initial_scores)
        self.assertTrue(success)

        # Verify initial
        s1 = self.mgr.get_scores("judge_disagreement_sample", "JD-0001")
        self.assertEqual(s1["socratic_guidance"], 1)
        self.assertEqual(s1["correctness"], False)

        # 2. Overwrite with new scores
        updated_scores = {"socratic_guidance": 3, "scaffolding": 2, "correctness": True}
        success, msg = self.mgr.save_scores("judge_disagreement_sample", "JD-0001", updated_scores)
        self.assertTrue(success)

        # Verify overwritten
        s2 = self.mgr.get_scores("judge_disagreement_sample", "JD-0001")
        self.assertEqual(s2["socratic_guidance"], 3)
        self.assertEqual(s2["scaffolding"], 2)
        self.assertEqual(s2["correctness"], True)

    def test_reset_and_empty_scores(self):
        # 1. Fill row
        initial_scores = {"socratic_guidance": 2, "correctness": True, "overall_score_out_of_5": 3.5}
        self.mgr.save_scores("judge_disagreement_sample", "JD-0002", initial_scores)
        self.assertTrue(self.mgr.get_all_status("judge_disagreement_sample")["JD-0002"])

        # 2. Reset and save empty scores (all None)
        empty_scores = {k: None for k, _, _, _ in METRIC_COLUMNS}
        success, msg = self.mgr.save_scores("judge_disagreement_sample", "JD-0002", empty_scores)
        self.assertTrue(success)
        self.assertIn("Emptied/cleared", msg)

        # Verify row is now empty
        read_scores = self.mgr.get_scores("judge_disagreement_sample", "JD-0002")
        self.assertIsNone(read_scores)
        self.assertFalse(self.mgr.get_all_status("judge_disagreement_sample")["JD-0002"])

    def test_validation_bounds(self):
        # Invalid integer metric > 3
        bad_scores = {"socratic_guidance": 4}
        success, msg = self.mgr.save_scores("judge_disagreement_sample", "JD-0001", bad_scores)
        self.assertFalse(success)
        self.assertIn("between 0 and 3", msg)

        # Invalid overall score out of 5 > 5.0
        bad_scores = {"overall_score_out_of_5": 6.0}
        success, msg = self.mgr.save_scores("judge_disagreement_sample", "JD-0001", bad_scores)
        self.assertFalse(success)
        self.assertIn("between 0.0 and 5.0", msg)


class TestServerAPI(unittest.TestCase):
    """Test HTTP Server endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.base_dir = Path(__file__).resolve().parent.parent
        cls.temp_dir = tempfile.mkdtemp()
        cls.temp_excel_dir = Path(cls.temp_dir)
        orig_excel_dir = cls.base_dir / "misc" / "annotation_excel_files"
        for f in orig_excel_dir.glob("*.xlsx"):
            shutil.copy(f, cls.temp_excel_dir / f.name)

        cls.data_loader = AnnotationDataLoader(cls.base_dir)
        cls.excel_manager = ExcelAnnotationManager(cls.temp_excel_dir)
        cls.static_dir = cls.base_dir / "annotation_ui" / "static"

        AnnotationRequestHandler.data_loader = cls.data_loader
        AnnotationRequestHandler.excel_manager = cls.excel_manager
        AnnotationRequestHandler.static_dir = cls.static_dir

        cls.port = 8999
        cls.server = ThreadingHTTPServer(("127.0.0.1", cls.port), AnnotationRequestHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.temp_dir)

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            return resp.status, resp.headers.get("Content-Type"), data

    def _post_json(self, path, payload):
        url = f"http://127.0.0.1:{self.port}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            return resp.status, json.loads(data.decode("utf-8"))

    def test_serve_index_html(self):
        status, ctype, data = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn(b"Socratic AI Annotation Studio", data)

    def test_serve_static_assets(self):
        status, ctype, data = self._get("/static/style.css")
        self.assertEqual(status, 200)
        self.assertIn(b":root", data)

        status, ctype, data = self._get("/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn(b"loadConversation", data)

    def test_api_samples(self):
        status, ctype, data = self._get("/api/samples")
        self.assertEqual(status, 200)
        body = json.loads(data.decode("utf-8"))
        self.assertIn("samples", body)
        self.assertEqual(len(body["samples"]), 3)

    def test_api_conversations(self):
        status, ctype, data = self._get("/api/conversations?sample=random_sample")
        self.assertEqual(status, 200)
        body = json.loads(data.decode("utf-8"))
        self.assertEqual(body["total"], 240)
        self.assertEqual(body["conversations"][0]["id"], "RND-0001")

    def test_api_conversation_detail(self):
        status, ctype, data = self._get("/api/conversation?sample=random_sample&id=RND-0001")
        self.assertEqual(status, 200)
        body = json.loads(data.decode("utf-8"))
        self.assertEqual(body["annotation_id"], "RND-0001")
        self.assertEqual(body["index"], 1)
        self.assertEqual(body["next_id"], "RND-0002")
        self.assertIn("record", body)

    def test_api_rubric(self):
        status, ctype, data = self._get("/api/rubric")
        self.assertEqual(status, 200)
        body = json.loads(data.decode("utf-8"))
        self.assertIn("rubric", body)
        self.assertIn("socratic_guidance", body["rubric"])

    def test_api_save(self):
        payload = {
            "sample_key": "metric_profile_sample",
            "annotation_id": "MP-0001",
            "scores": {
                "socratic_guidance": 3,
                "scaffolding": 3,
                "state_adaptation": 2,
                "diagnosis": 3,
                "student_agency": 2,
                "progression": 3,
                "coherence": 3,
                "correctness": True,
                "overall_score_out_of_5": 4.0,
                "overall_score_out_of_10": 8.0,
            },
        }
        status, body = self._post_json("/api/save", payload)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertTrue(body["is_graded"])
        self.assertEqual(body["next_id"], "MP-0002")

    def test_api_overwrite_and_empty_row(self):
        # 1. Overwrite MP-0001 with new scores
        payload = {
            "sample_key": "metric_profile_sample",
            "annotation_id": "MP-0001",
            "scores": {
                "socratic_guidance": 1,
                "scaffolding": 1,
                "correctness": False,
                "overall_score_out_of_5": 2.0,
                "overall_score_out_of_10": 4.0,
            },
        }
        status, body = self._post_json("/api/save", payload)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertTrue(body["is_graded"])

        # Check conversation endpoint returns updated scores
        status, _, data = self._get("/api/conversation?sample=metric_profile_sample&id=MP-0001")
        self.assertEqual(status, 200)
        cdata = json.loads(data.decode("utf-8"))
        self.assertEqual(cdata["saved_scores"]["socratic_guidance"], 1)
        self.assertEqual(cdata["saved_scores"]["correctness"], False)

        # 2. Reset / empty scores for MP-0001
        empty_payload = {
            "sample_key": "metric_profile_sample",
            "annotation_id": "MP-0001",
            "scores": {
                "socratic_guidance": None,
                "scaffolding": None,
                "state_adaptation": None,
                "diagnosis": None,
                "student_agency": None,
                "progression": None,
                "coherence": None,
                "correctness": None,
                "overall_score_out_of_5": None,
                "overall_score_out_of_10": None,
            },
        }
        status, body = self._post_json("/api/save", empty_payload)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertFalse(body["is_graded"])
        self.assertIn("Emptied/cleared", body["message"])

        # Verify conversation endpoint returns None for saved_scores and is_graded is False
        status, _, data = self._get("/api/conversation?sample=metric_profile_sample&id=MP-0001")
        self.assertEqual(status, 200)
        cdata = json.loads(data.decode("utf-8"))
        self.assertIsNone(cdata["saved_scores"])
        self.assertFalse(cdata["is_graded"])


if __name__ == "__main__":
    unittest.main()
