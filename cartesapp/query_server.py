"""Query-only HTTP server mode for cartesapp.

Instead of connecting to a Cartesi node and polling its ``/finish`` endpoint
(see ``cartesi.rollup.HTTPRollupServer``), this serves *only* queries
(inspects) directly over a plain HTTP server, in-process, with no Cartesi
machine or node.

The whole query lifecycle is reused: each HTTP request is turned into a
``RollupResponse(request_type='inspect_state')`` and fed to ``App._handle``,
which routes it through the URL/JSON/JSON-RPC routers exactly as it would for a
real inspect. Reports emitted by the query (via ``Context.rollup.report(...)``)
are captured by :class:`QueryRollup` and returned in a Cartesi-node-compatible
JSON envelope, so the generated frontend works against this server with no code
changes -- it only needs its node URL pointed here.

Note on concurrency: a single :class:`QueryRollup` instance buffers reports for
the request currently being handled, and Pony ORM's sqlite ``:memory:``
connection is not shared across threads. Request handling is therefore
serialized by using a single-threaded ``HTTPServer``.
"""

import json
import logging
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

from cartesi.models import RollupResponse, RollupData
from cartesi.rollup import Rollup

LOGGER = logging.getLogger(__name__)

# Dummy application address handed back by the /rpc stub so the frontend's
# getAppAddress() resolves. The /inspect handler ignores the address segment.
DUMMY_APP_ADDRESS = "0x0000000000000000000000000000000000000001"
DUMMY_CHAIN_ID = 13370

_INSPECT_PATH = re.compile(r"^/inspect(/.*)?$")


class QueryRollup(Rollup):
    """A :class:`cartesi.rollup.Rollup` that buffers reports in memory.

    Only ``report`` is meaningful for inspects; notices/vouchers/gio are not
    valid during an inspect and raise, mirroring the real node's behavior.
    """

    def __init__(self):
        super().__init__()
        self.reports: list[str] = []
        self.exception: str | None = None

    def reset(self):
        self.reports = []
        self.exception = None

    def main_loop(self):  # pragma: no cover - unused; HTTP handler drives _handle
        raise NotImplementedError("QueryRollup does not poll; it is driven per HTTP request")

    def report(self, payload: str) -> bytes | None:
        # payload is already a '0x..' hex string (output.send_report -> bytes2hex)
        self.reports.append(payload)
        return None

    def notice(self, payload: str) -> bytes | None:
        raise RuntimeError("notice is not allowed during a query (inspect)")

    def voucher(self, payload: dict) -> bytes | None:
        raise RuntimeError("voucher is not allowed during a query (inspect)")

    def delegate_call_voucher(self, payload: dict) -> bytes | None:
        raise RuntimeError("delegate_call_voucher is not allowed during a query (inspect)")

    def gio(self, payload: dict) -> bytes | None:
        raise RuntimeError("gio is not allowed during a query (inspect)")


def _make_handler(rollup: QueryRollup, app):
    """Build a BaseHTTPRequestHandler bound to a rollup + cartesi App."""

    class QueryRequestHandler(BaseHTTPRequestHandler):
        # --- helpers -------------------------------------------------------
        def _set_cors_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")

        def _send_json(self, status_code: int, body: dict):
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self._set_cors_headers()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", 0) or 0)
            return self.rfile.read(length) if length > 0 else b""

        # --- http verbs ----------------------------------------------------
        def do_OPTIONS(self):  # noqa: N802 (BaseHTTPRequestHandler API)
            self.send_response(204)
            self._set_cors_headers()
            self.end_headers()

        def do_GET(self):  # noqa: N802
            # Allow GET /inspect/<app>/<path> for url-format convenience.
            match = _INSPECT_PATH.match(self.path.split("?", 1)[0])
            if match is None:
                self._send_json(404, {"error": "not found"})
                return
            # For GET, the inspect payload is the path after /inspect/<app>/.
            # Strip '/inspect/<app>/' -> remaining path + query string.
            raw = self.path[len("/inspect/"):]
            # drop the leading app-address segment
            parts = raw.split("/", 1)
            payload = parts[1] if len(parts) > 1 else ""
            self._handle_inspect(payload.encode("utf-8"))

        def do_POST(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            body = self._read_body()
            if path == "/rpc":
                self._handle_rpc(body)
                return
            if _INSPECT_PATH.match(path) is not None:
                self._handle_inspect(body)
                return
            self._send_json(404, {"error": "not found"})

        # --- core ----------------------------------------------------------
        def _handle_inspect(self, body: bytes):
            # The Cartesi node forwards the raw request body bytes as the
            # inspect payload; RollupData.payload must be a '0x..' hex string.
            payload_hex = "0x" + body.hex()
            response = RollupResponse(
                request_type="inspect_state",
                data=RollupData(payload=payload_hex),
            )
            rollup.reset()
            try:
                status = app._handle(response)
            except Exception as exc:  # defensive; _handle already catches most
                LOGGER.exception("Error handling inspect")
                rollup.exception = str(exc)
                status = False
            self._send_json(
                200,
                {
                    "status": "Accepted" if status else "Rejected",
                    "exception_payload": rollup.exception,
                    "reports": [{"payload": p} for p in rollup.reports],
                    "processed_input_count": 0,
                },
            )

        def _handle_rpc(self, body: bytes):
            # Minimal JSON-RPC stub so the generated frontend's getAppAddress()
            # (cartesi_getApplication) and a few siblings resolve. The address
            # is a fixed dummy; the /inspect handler ignores it.
            try:
                req = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                self._send_json(200, {"jsonrpc": "2.0", "id": None,
                                      "error": {"code": -32700, "message": "Parse error"}})
                return
            req_id = req.get("id")
            method = req.get("method")
            result = self._rpc_result(method)
            if result is _RPC_UNKNOWN:
                self._send_json(200, {
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                })
                return
            self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": result})

        @staticmethod
        def _rpc_result(method):
            if method == "cartesi_getApplication":
                return {
                    "name": "app",
                    "applicationAddress": DUMMY_APP_ADDRESS,
                    "state": "ENABLED",
                }
            if method == "cartesi_getChainId":
                return DUMMY_CHAIN_ID
            if method == "cartesi_getNodeVersion":
                return "cartesapp-query-server"
            if method == "cartesi_getProcessedInputCount":
                return 0
            return _RPC_UNKNOWN

        def log_message(self, fmt, *args):  # route access logs into our logger
            LOGGER.debug("%s - %s", self.address_string(), fmt % args)

    return QueryRequestHandler


# sentinel for unknown rpc methods
_RPC_UNKNOWN = object()


def run_query_server(rollup: QueryRollup, app, host: str = "0.0.0.0", port: int = 8090):
    """Serve queries over a (single-threaded) HTTP server until interrupted."""
    handler_cls = _make_handler(rollup, app)
    server = HTTPServer((host, port), handler_cls)
    LOGGER.info("cartesapp query-server listening on http://%s:%d", host, port)
    print(f"cartesapp query-server listening on http://{host}:{port} (inspect: POST /inspect/<app>)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Shutting down query-server")
    finally:
        server.server_close()
