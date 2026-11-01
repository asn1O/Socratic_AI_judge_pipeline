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
        "description": "Determine whether the tutor's reasoning, explanations, calculations, guidance, and conclusions are correct with respect to the problem and the student's situation.",
        "levels": {
            "TRUE": "Tutor's substantive content is correct.",
            "FALSE": "Tutor makes a substantive factual, mathematical, logical, or conceptual error.",
        },
    },
    "socratic_guidance": {
        "title": "Socratic Guidance",
        "type": "scale_0_3",
        "description": "Evaluate the method of guidance used by the tutor. Focus specifically on whether the tutor guides reasoning primarily through questions that elicit thinking, or through statements that provide answers.",
        "rule": "Do not use the amount of help provided as the basis for this score. Evaluate the method of guidance.",
        "levels": {
            "0": "0 = Very poor / absent: Almost all guidance is statements (answers, solution steps, corrections, explanations). Any questions are rhetorical or have the answer built into them.",
            "1": "1 = Weak: Some genuine questions, but statements or leading questions make up about half or more of the guidance. Tutor often asks and then answers it, or states the next step.",
            "2": "2 = Adequate: Most guidance is genuine questions requiring thinking, but at least once tutor states a step/conclusion student could have worked out, or asks a leading question.",
            "3": "3 = Strong: Essentially every substantive turn is a question requiring student reasoning, including at least one that asks student to justify/test their own idea. Tutor never states a conclusion student could reach.",
        },
    },
    "scaffolding": {
        "title": "Scaffolding",
        "type": "scale_0_3",
        "description": "Evaluate the granularity and amount of help provided by the tutor during each intervention. Focus on how much reasoning is supplied vs left for the student to work out.",
        "rule": "Do not use whether the tutor asks a question or makes a statement as the basis for this score. Evaluate the amount and granularity of assistance.",
        "levels": {
            "0": "0 = Very poor / absent: Provides the full solution, final answer, or performs the central step for the student.",
            "1": "1 = Weak: Names the key method or sets up the problem, so student's central decision is made for them; student only carries it out.",
            "2": "2 = Adequate: Gives useful partial direction (points to concept/step) and student makes central inference, but help is larger than needed or comes before student had a chance to try.",
            "3": "3 = Strong: Gives smallest nudge that could work (e.g. redirecting attention), escalating only if stuck. Central reasoning left entirely to student.",
        },
    },
    "state_adaptation": {
        "title": "State Adaptation",
        "type": "scale_0_3",
        "description": "Evaluate how well the tutor responds to the student's current understanding, mistakes, confusion, and progress.",
        "levels": {
            "0": "0 = Very poor / absent: Responses do not depend on what the student said. Follows a script or repeats a move that already failed.",
            "1": "1 = Weak: Acknowledges student response ('good', 'not quite') but next move is generic and could be given to any answer.",
            "2": "2 = Adequate: Most replies address student's specific error/step, but at least one important thing is missed (error unaddressed, step unacknowledged, or pace not adjusted).",
            "3": "3 = Strong: Every reply is tied to student's specific words/reasoning, targets exact misconception, changes approach when something fails, and adjusts pace to student level.",
        },
    },
    "diagnosis": {
        "title": "Diagnosis",
        "type": "scale_0_3",
        "description": "Evaluate how well the tutor identifies and investigates what the student currently understands, misunderstands, or is unable to do.",
        "levels": {
            "0": "0 = Very poor / absent: No attempt to find out what student thinks. Tutor acts on assumptions.",
            "1": "1 = Weak: Only generic checks ('Do you understand?'), or inference about difficulty is wrong/unsupported, or tells student what is wrong without probing reasoning.",
            "2": "2 = Adequate: Accurately identifies main difficulty from student answers, but does not confirm it by asking to explain, or doesn't distinguish slip from misconception.",
            "3": "3 = Strong: Asks targeted questions bringing out student's reasoning, accurately identifies root cause (slip vs misconception vs prerequisite), and confirms before intervening.",
        },
    },
    "student_agency": {
        "title": "Student Agency",
        "type": "scale_0_3",
        "description": "Evaluate who performs the intellectual heavy lifting throughout the conversation. Focus on whether student generates, connects, tests, and articulates the key reasoning.",
        "rule": "Do not use the number of tutor questions as the basis for this score. Evaluate who actually performs the reasoning.",
        "levels": {
            "0": "0 = Very poor / absent: Tutor produces nearly all key reasoning. Student confirms, copies, or says 'ok'.",
            "1": "1 = Weak: Student produces some steps, but tutor chooses strategy or makes central inference. Student turns are short or echo tutor.",
            "2": "2 = Adequate: Student produces most steps including strategy/central inference, but tutor supplies at least one key step or student depends on tutor's wording.",
            "3": "3 = Strong: Student produces central reasoning, makes connections on their own, self-corrects, and explains in own words. Tutor supplies no key step.",
        },
    },
    "progression": {
        "title": "Progression",
        "type": "scale_0_3",
        "description": "Evaluate whether the conversation moves the student meaningfully toward understanding and solving the problem.",
        "levels": {
            "0": "0 = Very poor / absent: No progress, or student ends more confused than they started.",
            "1": "1 = Weak: Partial progress: some steps completed or misconception partly addressed, but solution is incomplete or major gap remains at the end.",
            "2": "2 = Adequate: Student reaches or is near correct solution, but no evidence they understand why (no explanation, check, or transfer), or happened only with heavy support.",
            "3": "3 = Strong: Student reaches correct solution through own reasoning and shows understanding: explains why, states principle, or handles variant.",
        },
    },
    "coherence": {
        "title": "Coherence",
        "type": "scale_0_3",
        "description": "Evaluate the logical and conversational consistency of the dialogue.",
        "levels": {
            "0": "0 = Very poor / absent: Frequently contradictory or off-topic. Replies are often unrelated to previous turn.",
            "1": "1 = Weak: Noticeable problems: a contradiction, unanswered student question, purposeless repetition, or uncorrected tutor error affecting dialogue.",
            "2": "2 = Adequate: Mostly coherent with one or two minor issues (slight redundancy, brief tangent, minor slip) not affecting logic.",
            "3": "3 = Strong: Every turn follows from the previous one. No contradictions, repetition, or ignored questions.",
        },
    },
    "overall_score_out_of_5": {
        "title": "Overall Score (out of 5)",
        "type": "decimal",
        "description": "Holistic assessment of pedagogical effectiveness on a 0.0 to 5.0 scale.",
    },
    "overall_score_out_of_10": {
        "title": "Overall Score (out of 10)",
        "type": "decimal",
        "description": "Comprehensive rating on a 0.0 to 10.0 scale (conveniently auto-scaled as 2x the 5-point score, or custom).",
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
                valid_ids = self.data_loader.get_id_list(key)
                summary = self.excel_manager.get_sample_summary(key, valid_ids=valid_ids)
                results.append({
                    "key": key,
                    "display_name": meta.get("display_name", key),
                    "id_prefix": meta.get("id_prefix", ""),
                    "description": meta.get("description", ""),
                    "total": len(valid_ids),
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

            valid_ids = self.data_loader.get_id_list(sample_key)
            if annotation_id not in valid_ids:
                self._send_json({"error": f"Annotation ID '{annotation_id}' is not in the active annotation set."}, status=HTTPStatus.BAD_REQUEST)
                return

            success, message = self.excel_manager.save_scores(sample_key, annotation_id, scores)
            if not success:
                self._send_json({"success": False, "error": message}, status=HTTPStatus.BAD_REQUEST)
                return

            # Compute next ID to make transition immediate
            conv_info = self.data_loader.get_conversation_by_id(sample_key, annotation_id)
            next_id = conv_info.get("next_id") if conv_info else None
            valid_ids = self.data_loader.get_id_list(sample_key)
            summary = self.excel_manager.get_sample_summary(sample_key, valid_ids=valid_ids)
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
