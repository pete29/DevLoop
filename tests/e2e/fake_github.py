"""A GitHub that lives in this process, for the end-to-end tests.

It answers the REST calls DevLoop's allow list permits, over
real HTTP on localhost, so the request code, the allow list
and the JSON handling are all the real ones. State is a few
dicts the test can read and change: merging a pull request
is a human's act on GitHub, so the test does it here.
"""

import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def now() -> str:

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeGitHub:

    def __init__(self, owner: str, repository: str) -> None:

        self.owner = owner
        self.repository = repository
        self.issues: dict[int, dict] = {}
        self.pulls: dict[int, dict] = {}
        self.comments: dict[int, list[str]] = {}
        self.calls: list[str] = []
        self.next_number = 1

        fake = self

        class Handler(BaseHTTPRequestHandler):

            def log_message(self, *args) -> None:  # quiet
                pass

            def do_GET(self) -> None:
                fake.handle(self, "GET")

            def do_POST(self) -> None:
                fake.handle(self, "POST")

            def do_PATCH(self) -> None:
                fake.handle(self, "PATCH")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:

        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self) -> "FakeGitHub":

        self.thread.start()

        return self

    def __exit__(self, *exc) -> None:

        self.server.shutdown()

        self.server.server_close()

    # ------------------------------------------------ state

    def html(self, kind: str, number: int) -> str:

        return f"https://github.com/{self.owner}/{self.repository}/{kind}/{number}"

    def add_issue(self, title: str, body: str) -> dict:

        number = self.next_number

        self.next_number += 1

        issue = {
            "id": 1000 + number,
            "number": number,
            "title": title,
            "body": body,
            "state": "open",
            "labels": [],
            "html_url": self.html("issues", number),
        }

        self.issues[number] = issue

        return issue

    def merge(self, number: int) -> None:

        self.pulls[number].update(state="closed", merged=True, merged_at=now())

    # ------------------------------------------------ HTTP

    def handle(self, request: BaseHTTPRequestHandler, method: str) -> None:

        parsed = urlparse(request.path)

        path = parsed.path

        query = parse_qs(parsed.query)

        length = int(request.headers.get("Content-Length") or 0)

        payload = json.loads(request.rfile.read(length) or b"{}") if length else {}

        self.calls.append(f"{method} {path}")

        status, body = self.route(method, path, query, payload)

        data = json.dumps(body).encode()

        request.send_response(status)

        request.send_header("Content-Type", "application/json")

        request.send_header("Content-Length", str(len(data)))

        request.end_headers()

        request.wfile.write(data)

    def route(self, method: str, path: str, query: dict, payload: dict):

        base = f"/repos/{self.owner}/{self.repository}"

        if path == base and method == "GET":
            return 200, {"default_branch": "main", "full_name": f"{self.owner}/{self.repository}"}

        if path == f"{base}/issues" and method == "GET":
            return 200, [issue for issue in self.issues.values() if issue["state"] == "open"]

        if path == f"{base}/issues" and method == "POST":
            return 201, self.add_issue(payload["title"], payload.get("body", ""))

        found = re.fullmatch(rf"{base}/issues/(\d+)", path)

        if found:

            issue = self.issues.get(int(found.group(1)))

            if issue is None:
                return 404, {"message": "Not Found"}

            if method == "PATCH":
                issue.update(
                    {key: value for key, value in payload.items() if key in ("state", "labels")}
                )
                issue["labels"] = [{"name": name} if isinstance(name, str) else name for name in issue["labels"]]

            return 200, issue

        found = re.fullmatch(rf"{base}/issues/(\d+)/comments", path)

        if found:

            number = int(found.group(1))

            if method == "POST":
                self.comments.setdefault(number, []).append(payload["body"])
                return 201, {"html_url": f"{self.html('issues', number)}#comment"}

            return 200, [{"body": body, "user": {"login": "someone"}} for body in self.comments.get(number, [])]

        if path == f"{base}/pulls" and method == "POST":

            number = self.next_number

            self.next_number += 1

            pull = {
                "number": number,
                "title": payload["title"],
                "body": payload.get("body", ""),
                "state": "open",
                "merged": False,
                "merged_at": None,
                "html_url": self.html("pull", number),
                "head": {"ref": payload["head"], "sha": "0" * 40},
                "base": {"ref": payload["base"]},
                "created_at": now(),
            }

            self.pulls[number] = pull

            return 201, pull

        if path == f"{base}/pulls" and method == "GET":

            head = (query.get("head") or [""])[0].split(":")[-1]

            return 200, [pull for pull in self.pulls.values() if not head or pull["head"]["ref"] == head]

        found = re.fullmatch(rf"{base}/pulls/(\d+)", path)

        if found:

            pull = self.pulls.get(int(found.group(1)))

            if pull is None:
                return 404, {"message": "Not Found"}

            if method == "PATCH":
                pull.update({key: value for key, value in payload.items() if key in ("title", "body")})

            return 200, pull

        if re.fullmatch(rf"{base}/pulls/\d+/(comments|reviews)", path):
            return 200, []

        if path == f"{base}/actions/runs":
            return 200, {"workflow_runs": []}

        return 404, {"message": f"The fake GitHub does not know {method} {path}"}
