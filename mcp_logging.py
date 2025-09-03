import json
import logging
import os
import sys
import time
import traceback
import uuid
from typing import Dict, Optional, Set, Any, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from datadog_api_client.v2 import ApiClient, ApiException, Configuration
from datadog_api_client.v2.api import logs_api
from datadog_api_client.v2.models import HTTPLog, HTTPLogItem


# =============================================================================
# Datadog Handler
# =============================================================================


class DatadogHandler(logging.Handler):
    def __init__(
        self,
        service_name: str,
        ddsource: str = "mcp-server",
        dd_site: Optional[str] = None,
    ):

        super().__init__()

        api_key = os.getenv("DD_API_KEY")
        if not api_key:
            raise ValueError(
                "DD_API_KEY environment variable is required for DatadogHandler"
            )

        self.service_name = service_name
        self.ddsource = ddsource
        self.environment = os.getenv("ENVIRONMENT", "development")

        self.configuration = Configuration()
        if dd_site:
            self.configuration.server_variables["site"] = dd_site
        elif os.getenv("DD_SITE"):
            self.configuration.server_variables["site"] = os.getenv("DD_SITE")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)

            tags = [
                f"env:{self.environment}",
                f"service:{self.service_name}",
                f"source:{self.ddsource}",
                f"logger:{record.name}",
                f"level:{record.levelname.lower()}",
            ]

            extra_fields = {
                k: v
                for k, v in record.__dict__.items()
                if k not in JSONFormatter.EXCLUDED_FIELDS and not k.startswith("_")
            }

            if hasattr(record, "jsonrpc_method") and record.jsonrpc_method:
                tags.append(f"method:{record.jsonrpc_method}")
            if hasattr(record, "request_id") and record.request_id:
                tags.append(f"request_id:{record.request_id}")
            if hasattr(record, "request_type") and record.request_type:
                tags.append(f"request_type:{record.request_type}")

            ddtags = ",".join(tags)

            with ApiClient(self.configuration) as api_client:
                api_instance = logs_api.LogsApi(api_client)
                body = HTTPLog(
                    [
                        HTTPLogItem(
                            ddsource=self.ddsource,
                            ddtags=ddtags,
                            message=message,
                            service=self.service_name,
                        )
                    ]
                )

                api_instance.submit_log(body)

        except ApiException as e:
            print(f"Failed to send log to Datadog: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error in DatadogHandler: {e}", file=sys.stderr)


# =============================================================================
# JSON Formatter
# =============================================================================


class JSONFormatter(logging.Formatter):

    EXCLUDED_FIELDS: Set[str] = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "getMessage",
        "taskName",
    }

    def __init__(self, service_name: str = "mcp-server"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.%f")
        if not timestamp.endswith("Z"):
            timestamp += "Z"

        log_entry = {
            "@timestamp": timestamp,
            "service": self.service_name,
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "host": os.getenv("HOSTNAME", "unknown"),
        }

        if record.exc_info:
            log_entry["error"] = {
                "kind": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stack": (
                    self.formatException(record.exc_info) if record.exc_info else None
                ),
            }

        extra_fields = {
            k: v for k, v in record.__dict__.items() if k not in self.EXCLUDED_FIELDS
        }
        if extra_fields:
            log_entry.update(extra_fields)

        return json.dumps(log_entry, default=str, ensure_ascii=False)


# =============================================================================
# MCP Logging Middleware
# =============================================================================


class MCPLoggingMiddleware(BaseHTTPMiddleware):
    DEFAULT_BUSINESS_METHODS = {"tools/call", "prompts/get", "resources/read"}

    def __init__(
        self,
        app,
        include_payloads: Optional[bool] = None,
        business_logs_only: Optional[bool] = None,
        business_methods: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self.logger = logging.getLogger("mcp.middleware")

        self.include_payloads = (
            include_payloads
            if include_payloads is not None
            else os.getenv("LOG_INCLUDE_PAYLOADS", "true").lower() == "true"
        )
        self.business_logs_only = (
            business_logs_only
            if business_logs_only is not None
            else os.getenv("BUSINESS_LOGS_ONLY", "true").lower() == "true"
        )
        self.business_methods = business_methods or self.DEFAULT_BUSINESS_METHODS

    def _should_log(self, method_name: Optional[str]) -> bool:
        if self.business_logs_only:
            return method_name in self.business_methods
        return True

    def _get_client_ip(self, request) -> Optional[str]:
        forwarded = request.headers.get("x-forwarded-for")
        return (
            forwarded.split(",")[0].strip()
            if forwarded
            else getattr(request.client, "host", None)
        )

    def _parse_jsonrpc(
        self, content: bytes
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not content:
            return None, None
        try:
            parsed = json.loads(content.decode())
            if isinstance(parsed, dict):
                return parsed, parsed.get("method")
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                return parsed, parsed[0].get("method")
            return parsed, None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, None

    def _add_payload(
        self,
        log_entry: Dict[str, Any],
        content: bytes,
        parsed: Optional[Dict[str, Any]],
    ) -> None:
        if not self.include_payloads:
            return

        if parsed:
            log_entry["payload"] = parsed
        elif content:
            raw = content.decode(errors="ignore")
            log_entry["raw_payload"] = raw[:2000] + "..." if len(raw) > 2000 else raw

    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.time()

        request_body = await request.body()
        parsed_request, method_name = self._parse_jsonrpc(request_body)

        should_log = self._should_log(method_name)

        if should_log:
            request_log = {
                "request_id": request_id,
                "request_type": "request",
                "http_method": request.method,
                "path": request.url.path,
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
                "content_length": len(request_body) if request_body else 0,
                "jsonrpc_method": method_name,
            }
            self._add_payload(request_log, request_body, parsed_request)
            self.logger.info("MCP Request", extra=request_log)

        try:
            response = await call_next(request)

            response_body = b"".join([chunk async for chunk in response.body_iterator])
            duration_ms = round((time.time() - start_time) * 1000, 2)

            if should_log:
                parsed_response, _ = self._parse_jsonrpc(response_body)
                response_log = {
                    "request_id": request_id,
                    "request_type": "response",
                    "status_code": response.status_code,
                    "response_size": len(response_body),
                    "duration_ms": duration_ms,
                    "jsonrpc_method": method_name,
                }

                has_jsonrpc_error = (
                    parsed_response
                    and isinstance(parsed_response, dict)
                    and "error" in parsed_response
                )
                if has_jsonrpc_error:
                    response_log["jsonrpc_error"] = parsed_response["error"]

                self._add_payload(response_log, response_body, parsed_response)

                if response.status_code >= 400 or has_jsonrpc_error:
                    self.logger.error("MCP Response", extra=response_log)
                else:
                    self.logger.info("MCP Response", extra=response_log)

            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            error_log = {
                "request_id": request_id,
                "request_type": "error",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "duration_ms": duration_ms,
                "jsonrpc_method": method_name,
                "traceback": traceback.format_exc(),
            }
            self.logger.error("MCP Error", extra=error_log)
            raise


# =============================================================================
# Logging Setup
# =============================================================================


def setup_logging(
    service_name: str = "mcp-server",
    enable_datadog: Optional[bool] = None,
    datadog_source: str = "fly-mcp",
) -> None:
    is_production = _is_production_environment()
    use_json_logging = _should_use_json_logging()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    if use_json_logging:
        console_handler.setFormatter(JSONFormatter(service_name))
    else:
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    root_logger.addHandler(console_handler)

    datadog_enabled = False
    if enable_datadog is None:
        enable_datadog = bool(os.getenv("DD_API_KEY"))

    if enable_datadog:
        try:
            datadog_handler = DatadogHandler(
                service_name=service_name, ddsource=datadog_source
            )
            datadog_handler.setFormatter(JSONFormatter(service_name))
            datadog_handler.setLevel(getattr(logging, log_level, logging.INFO))
            root_logger.addHandler(datadog_handler)
            datadog_enabled = True
        except Exception as e:
            print(f"Failed to initialize Datadog logging: {e}", file=sys.stderr)

    logging.getLogger(__name__).info("MCP Logging initialized")


def _is_production_environment() -> bool:
    return os.getenv("ENVIRONMENT", "development").lower() == "production"


def _should_use_json_logging() -> bool:
    return os.getenv("JSON_LOGS", "false").lower() == "true"


def setup_mcp_logging(
    service_name: str = "mcp-server",
    middleware_config: Optional[Dict[str, Any]] = None,
    enable_datadog: Optional[bool] = None,
    datadog_source: str = "fly-mcp",
) -> MCPLoggingMiddleware:
    setup_logging(service_name, enable_datadog, datadog_source)
    return MCPLoggingMiddleware(None, **(middleware_config or {}))
