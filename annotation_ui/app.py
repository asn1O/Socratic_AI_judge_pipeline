"""app.py - Lightweight HTTP server and REST API for the Socratic AI Annotation UI."""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import sys
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure annotation_ui directory is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
BASE_DIR = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from data_loader import AnnotationDataLoader, SAMPLES_META
from excel_manager import ExcelAnnotationManager, METRIC_COLUMNS

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("annotation_ui")

RUBRIC_GUIDELINES = {
    "correctness": {
        "title": "Correctness",
        "type": "boolean",
        "description": "Determine whether the tutor's substantive content, reasoning, calculations, and conclusions are factually and conceptually correct.",
        "levels": {
            "TRUE": "Tutor's substantive content is correct.",
            "FALSE": "Tutor makes a substantive factual, mathematical, logical, or conceptual error.",
        },
    },
    "socratic_guidance": {
        "title": "Socratic Guidance",
        "type": "scale_0_3",
        "description": "Evaluate whether the tutor guides primarily through questions that elicit thinking, or through statements that provide answers.",
        "levels": {
            "0": "Very poor / absent: Almost all guidance is statements or rhetorical questions with answers built in.",
            "1": "Weak: Some genuine questions, but statements or leading questions make up half or more of guidance.",
            "2": "Adequate: Most guidance is genuine questions, but at least once tutor states a step the student could have worked out.",
            "3": "Strong: Essentially every turn is a question requiring student reasoning; at least one asks to justify/test an idea.",
        },
    },
    "scaffolding": {
        "title": "Scaffolding",
        "type": "scale_0_3",
        "description": "Evaluate the granularity and amount of help provided. Focus on how much is supplied vs left for the student to work out.",
        "levels": {
            "0": "Very poor / absent: Provides full solution, final answer, or performs central step for the student.",
            "1": "Weak: Names key method or sets up problem so central decision is made for student; student only carries it out.",
            "2": "Adequate: Gives useful partial direction and student still makes central inference, but help is larger than needed or premature.",
            "3": "Strong: Gives smallest nudge that could work (redirects attention), escalating only if stuck. Central reasoning left to student.",
        },
    },
    "state_adaptation": {
        "title": "State Adaptation",
        "type": "scale_0_3",
        "description": "Evaluate how well the tutor responds to the student's current understanding, mistakes, confusion, and progress.",
        "levels": {
            "0": "Very poor / absent: Responses do not depend on student input (follows a rigid script or repeats failed moves).",
            "1": "Weak: Acknowledges response but next move is generic and could be given to any answer.",
            "2": "Adequate: Most replies address student's specific step/error, but at least one important signal is missed.",
            "3": "Strong: Every reply is tied to student's exact words/misconception, changes approach when stuck, and adjusts pace.",
        },
    },
    "diagnosis": {
        "title": "Diagnosis",
        "type": "scale_0_3",
        "description": "Evaluate how well the tutor identifies and investigates what the student understands, misunderstands, or cannot do.",
        "levels": {
            "0": "Very poor / absent: No attempt to find out what student thinks; acts on assumptions.",
            "1": "Weak: Only generic checks ('Do you understand?'), or incorrect inferences without probing reasoning.",
            "2": "Adequate: Accurately identifies difficulty from student answers, but does not confirm it or distinguish slips from misconceptions.",
            "3": "Strong: Targeted questions that reveal reasoning, accurately identifying cause (slip vs misconception) before intervening.",
        },
    },
    "student_agency": {
        "title": "Student Agency",
        "type": "scale_0_3",
        "description": "Evaluate who performs the intellectual heavy lifting throughout the conversation.",
        "levels": {
            "0": "Very poor / absent: Tutor produces nearly all key reasoning. Student merely confirms or says 'ok'.",
            "1": "Weak: Student produces minor steps, but tutor chooses strategy or makes central inference.",
            "2": "Adequate: Student produces most steps, but tutor supplies at least one key step, or student echoes tutor's wording.",
            "3": "Strong: Student produces central reasoning, connects ideas, self-corrects, and explains in own words.",
        },
    },
    "progression": {
        "title": "Progression",
        "type": "scale_0_3",
        "description": "Evaluate whether the dialogue moves the student meaningfully toward understanding and solving the problem.",
        "levels": {
            "0": "Very poor / absent: No progress, or student ends more confused than they started.",
            "1": "Weak: Partial progress on some steps, but solution is incomplete or major gap remains at the end.",
            "2": "Adequate: Student reaches or is near correct solution, but no evidence they understand why (or heavy tutor support).",
            "3": "Strong: Student reaches correct solution through own reasoning and shows understanding (explains why, states principle).",
        },
    },
    "coherence": {
        "title": "Coherence",
        "type": "scale_0_3",
        "description": "Evaluate the logical and conversational consistency of the dialogue.",
        "levels": {
            "0": "Very poor / absent: Frequently contradictory or off-topic. Replies unrelated to previous turns.",
            "1": "Weak: Noticeable problems (a contradiction, unanswered question, purposeless repetition, uncorrected error).",
            "2": "Adequate: Mostly coherent with only minor issues (slight redundancy or brief tangent) that do not break logic.",
            "3": "Strong: Every turn follows logically from the previous one; no contradictions, repetitions, or ignored questions.",
        },
    },
    "overall_score_out_of_5": {
        "title": "Overall Score (out of 5)",
        "type": "decimal",
        "description": "Holistic assessment of pedagogical effectiveness on a 0 to 5 scale (e.g. 0.0 - 5.0).",
    },
    "overall_score_out_of_10": {
        "title": "Overall Score (out of 10)",
        "type": "decimal",
        "description": "Comprehensive rating on a 0 to 10 scale (can be auto-scaled as 2x the 5-point score, or custom).",
    },
}


class AnnotationRequestHandler(SimpleHTTPRequestHandler):
    """Custom request handler serving static files and REST API."""

    data_loader: AnnotationDataLoader
    excel_manager: ExcelAnnotationManager
    static_dir: Path

    def __init__(self, *args, **kwargs):
        # Serve static directory by default for standard requests
        super().__init__(*args, directory=str(self.static_dir), **kwargs)

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path.startswith("/api/"):
            self._handle_api_get(path, query_params)
        elif path in ("/", "/index.html"):
            self._serve_file(self.static_dir / "index.html", "text/html; charset=utf-8")
        elif path.startswith("/static/"):
            rel_file = path[len("/static/"):].lstrip("/")
            file_path = (self.static_dir / rel_file).resolve()
            # Security check: ensure path is within static_dir
            if str(file_path).startswith(str(self.static_dir.resolve())) and file_path.is_file():
                content_type, _ = mimetypes.guess_type(str(file_path))
                self._serve_file(file_path, content_type or "application/octet-stream")
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
        else:
            file_path = (self.static_dir / path.lstrip("/")).resolve()
            if str(file_path).startswith(str(self.static_dir.resolve())) and file_path.is_file():
                content_type, _ = mimetypes.guess_type(str(file_path))
                self._serve_file(file_path, content_type or "application/octet-stream")
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path.startswith("/api/"):
            self._handle_api_post(path)
        else:
            self._send_json({"error": "Not Found"}, status=HTTPStatus.NOT_FOUND)

    def _handle_api_get(self, path: str, query: Dict[str, list[str]]) -> None:
        if path == "/api/samples":
            results = []
            for key in self.data_loader.get_sample_keys():
                meta = self.data_loader.get_sample_meta(key) or {}
                summary = self.excel_manager.get_sample_summary(key)
                results.append({
                    "key": key,
                    "display_name": meta.get("display_name", key),
                    "id_prefix": meta.get("id_prefix", ""),
                    "description": meta.get("description", ""),
                    "total": summary["total"] or len(self.data_loader.get_id_list(key)),
                    "graded": summary["graded"],
                    "pending": summary["pending"],
                    "pct_completed": summary["pct_completed"],
                })
            self._send_json({"samples": results})

        elif path == "/api/conversations":
            sample = query.get("sample", [""])[0]
            if not sample or sample not in SAMPLES_META:
                self._send_json({"error": "Invalid or missing 'sample' parameter"}, status=HTTPStatus.BAD_REQUEST)
                return

            id_list = self.data_loader.get_id_list(sample)
            status_map = self.excel_manager.get_all_status(sample)
            items = [{"id": ann_id, "is_graded": status_map.get(ann_id, False)} for ann_id in id_list]
            self._send_json({"sample": sample, "total": len(items), "conversations": items})

        elif path == "/api/conversation":
            sample = query.get("sample", [""])[0]
            ann_id = query.get("id", [""])[0]
            idx_str = query.get("index", [""])[0]

            if not sample or sample not in SAMPLES_META:
                self._send_json({"error": "Invalid or missing 'sample' parameter"}, status=HTTPStatus.BAD_REQUEST)
                return

            data = None
            if ann_id:
                data = self.data_loader.get_conversation_by_id(sample, ann_id)
            elif idx_str.isdigit():
                data = self.data_loader.get_conversation_by_index(sample, int(idx_str))

            if not data:
                self._send_json({"error": f"Conversation not found for ID '{ann_id}'"}, status=HTTPStatus.NOT_FOUND)
                return

            current_id = data["record"].get("annotation_id", "")
            saved_scores = self.excel_manager.get_scores(sample, current_id)
            meta = self.data_loader.get_sample_meta(sample)

            response = {
                "sample": sample,
                "sample_meta": meta,
                "annotation_id": current_id,
                "index": data["index"],
                "total": data["total"],
                "prev_id": data["prev_id"],
                "next_id": data["next_id"],
                "record": data["record"],
                "saved_scores": saved_scores,
                "is_graded": saved_scores is not None,
            }
            self._send_json(response)

        elif path == "/api/rubric":
            self._send_json({"rubric": RUBRIC_GUIDELINES})

        else:
            self._send_json({"error": "Endpoint not found"}, status=HTTPStatus.NOT_FOUND)

    def _handle_api_post(self, path: str) -> None:
        if path == "/api/save":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(raw_body)
            except Exception as e:
                self._send_json({"error": f"Invalid JSON payload: {e}"}, status=HTTPStatus.BAD_REQUEST)
                return

            sample_key = payload.get("sample_key", "")
            annotation_id = payload.get("annotation_id", "")
            scores = payload.get("scores", {})

            if not sample_key or sample_key not in SAMPLES_META:
                self._send_json({"error": "Invalid or missing 'sample_key'"}, status=HTTPStatus.BAD_REQUEST)
                return
            if not annotation_id:
                self._send_json({"error": "Missing 'annotation_id'"}, status=HTTPStatus.BAD_REQUEST)
                return

            success, message = self.excel_manager.save_scores(sample_key, annotation_id, scores)
            if not success:
                self._send_json({"success": False, "error": message}, status=HTTPStatus.BAD_REQUEST)
                return

            # Compute next ID to make transition immediate
            conv_info = self.data_loader.get_conversation_by_id(sample_key, annotation_id)
            next_id = conv_info.get("next_id") if conv_info else None
            summary = self.excel_manager.get_sample_summary(sample_key)
            is_graded = any(v is not None and v != "" for v in scores.values())

            self._send_json({
                "success": True,
                "message": message,
                "annotation_id": annotation_id,
                "is_graded": is_graded,
                "next_id": next_id,
                "summary": summary,
            })
        else:
            self._send_json({"error": "Endpoint not found"}, status=HTTPStatus.NOT_FOUND)

    def _serve_file(self, filepath: Path, content_type: str) -> None:
        if not filepath.exists():
            self._send_json({"error": "File not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            logger.error("Failed to serve file %s: %s", filepath, e)
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))

    def _send_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    excel_dir = BASE_DIR / "misc" / "annotation_excel_files"
    data_loader = AnnotationDataLoader(BASE_DIR)
    excel_manager = ExcelAnnotationManager(excel_dir)
    static_dir = CURRENT_DIR / "static"

    AnnotationRequestHandler.data_loader = data_loader
    AnnotationRequestHandler.excel_manager = excel_manager
    AnnotationRequestHandler.static_dir = static_dir

    server_address = (host, port)
    try:
        httpd = ThreadingHTTPServer(server_address, AnnotationRequestHandler)
    except OSError as e:
        if e.errno == 98:  # Address already in use
            logger.warning("Port %d is already in use. Trying port %d...", port, port + 1)
            port += 1
            server_address = (host, port)
            httpd = ThreadingHTTPServer(server_address, AnnotationRequestHandler)
        else:
            raise

    url = f"http://{host}:{port}"
    print("\n" + "=" * 65)
    print("      SOCRATIC AI CONVERSATION ANNOTATION UI SERVER")
    print("=" * 65)
    print(f"Server is running at: {url}")
    print("Open the link in your web browser to start annotating.")
    print("Press Ctrl+C to stop the server.")
    print("=" * 65 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping annotation server...")
    finally:
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the Socratic AI Annotation UI Server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
