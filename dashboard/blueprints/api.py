import json

import requests as http_requests
from flask import current_app, jsonify, request

from dashboard.blueprints import bp as main
from dashboard.database import Application, Category, CustomCommand, get_db


@main.route("/api/reorder", methods=["POST"])
def api_reorder():
    data = request.get_json()
    if not data or "items" not in data or "type" not in data:
        return jsonify({"error": "Invalid payload"}), 400

    model = Application if data["type"] == "app" else Category
    if model not in (Application, Category):
        return jsonify({"error": "Invalid type"}), 400

    with get_db() as db:
        for i, item_id in enumerate(data["items"]):
            if not isinstance(item_id, int):
                continue
            obj = db.get(model, item_id)
            if obj:
                obj.sort_order = i
    return jsonify({"status": "ok"})


def _extract_value(data, template):
    """Extract value(s) from JSON data using a template.

    Template syntax:
      - Simple JSONPath-like: ``status``, ``data.count``, ``info.version``
      - Multiple fields:  ``Status: {status} | Users: {data.users.total}``
    """
    def _resolve(obj, path):
        def _resolve_key(target, key_path):
            for part in key_path.split("."):
                if part == "_len" and isinstance(target, list):
                    return len(target)
                if isinstance(target, dict):
                    target = target.get(part)
                elif isinstance(target, list):
                    try:
                        target = target[int(part)]
                    except (ValueError, IndexError):
                        return None
                else:
                    return None
            return target

        for key in path.split("."):
            if key == "_len" and isinstance(obj, list):
                return len(obj)

            if isinstance(obj, list):
                if key.startswith("max_by(") and key.endswith(")"):
                    field = key[len("max_by("):-1]
                    try:
                        obj = max(obj, key=lambda item: _resolve_key(item, field) or "")
                    except ValueError:
                        return None
                    continue
                if key.startswith("min_by(") and key.endswith(")"):
                    field = key[len("min_by("):-1]
                    try:
                        obj = min(obj, key=lambda item: _resolve_key(item, field) or "")
                    except ValueError:
                        return None
                    continue
                if key == "first":
                    obj = obj[0] if obj else None
                    continue
                if key == "last":
                    obj = obj[-1] if obj else None
                    continue
                try:
                    obj = obj[int(key)]
                except (ValueError, IndexError):
                    return None
                continue

            if isinstance(obj, dict):
                obj = obj.get(key)
            else:
                return None
        return obj

    if not template:
        # No template — return a compact summary
        if isinstance(data, list):
            return f"{len(data)} items"
        if isinstance(data, dict):
            parts = []
            for k, v in list(data.items())[:4]:
                parts.append(f"{k}: {v}" if not isinstance(v, (dict, list)) else f"{k}: ...")
            return " | ".join(parts)
        return str(data)[:120]

    # if template begins with "regex:", treat data as plain text and apply pattern
    if isinstance(data, str) and isinstance(template, str) and template.startswith("regex:"):
        import re

        pattern = template[len("regex:"):]
        m = re.search(pattern, data, re.S)
        if m:
            return m.group(1)
        return "—"

    # support value prefix for regex templates, e.g. "Power: regex:LOADPCT..."
    if isinstance(data, str) and isinstance(template, str) and "regex:" in template:
        import re

        prefix, pattern = template.split("regex:", 1)
        m = re.search(pattern, data, re.S)
        if m:
            return f"{prefix}{m.group(1)}"
        return prefix + "—"

    if "{" in template:
        import re

        def replacer(m):
            val = _resolve(data, m.group(1))
            return str(val) if val is not None else "—"

        return re.sub(r"\{([^}]+)\}", replacer, template)

    val = _resolve(data, template)
    return str(val) if val is not None else "—"


def _npm_get_hosts(base_url: str, identity: str, secret: str, verify: bool = True):
    """Authenticate with NPM and return /api/nginx/proxy-hosts JSON."""
    sess = http_requests.Session()
    if not verify:
        sess.verify = False

    auth = sess.post(
        base_url + "api/tokens",
        json={"identity": identity, "secret": secret},
        headers={"Accept": "application/json"},
    )
    auth.raise_for_status()
    token = auth.json().get("token")
    if not token:
        raise ValueError("failed to obtain NPM token")

    res = sess.get(
        base_url + "api/nginx/proxy-hosts",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    res.raise_for_status()
    return res.json()


@main.route("/api/app/<int:app_id>/stats")
def api_app_stats(app_id):
    with get_db() as db:
        app = db.get(Application, app_id)

    if not app or not app.api_url:
        return jsonify({"error": "No API configured"}), 404

    headers = {}
    if app.api_headers:
        try:
            headers = json.loads(app.api_headers)
            if not isinstance(headers, dict):
                headers = {}
        except (json.JSONDecodeError, TypeError):
            headers = {}

    try:
        method = app.api_method.upper() if app.api_method else "GET"
        # prepare request kwargs; include payload if provided for non-GET methods
        verify = getattr(app, "api_verify", True)
        kwargs = {"headers": headers, "timeout": 10, "verify": verify}
        payload_val = app.api_payload
        # special-case Nginx Proxy Manager: perform login flow if creds provided
        if app.api_url.endswith("/api/nginx/proxy-hosts") and payload_val:
            try:
                creds = json.loads(payload_val)
            except Exception:
                creds = {}
            # support both identity/secret and email/password naming
            if isinstance(creds, dict) and (
                ("identity" in creds and "secret" in creds) or
                ("email" in creds and "password" in creds)
            ):
                ident = creds.get("identity") or creds.get("email")
                secret = creds.get("secret") or creds.get("password")
                verify = not creds.get("ignore_tls", False)
                if not getattr(app, "api_verify", True):
                    verify = False
                data = _npm_get_hosts(
                    app.api_url.rsplit("/api/nginx/proxy-hosts", 1)[0] + "/",
                    ident,
                    secret,
                    verify,
                )
                display = _extract_value(data, app.api_value_template)
                return jsonify({"ok": True, "display": display})
        if payload_val and method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                kwargs["json"] = json.loads(payload_val)
            except Exception:
                kwargs["data"] = payload_val
        resp = http_requests.request(method, app.api_url, **kwargs)

        # LOGGING: dump status and body if not OK
        if not resp.ok:
            current_app.logger.warning(
                "API call to %s returned %s:\n%s",
                app.api_url,
                resp.status_code,
                resp.text,
            )

        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            # response isn't JSON – try to decode invalid bytes instead of failing
            body = None
            try:
                body = resp.content.decode(resp.encoding or "utf-8", errors="replace")
                data = json.loads(body)
            except Exception:
                data = body if body is not None else resp.text

        display = _extract_value(data, app.api_value_template)
        return jsonify({"ok": True, "display": display})

    except http_requests.RequestException as exc:
        return jsonify({"ok": False, "display": f"Error: {exc.__class__.__name__}"})


@main.route("/api/apps")
def api_apps():
    """Return all apps that have an API URL configured (used by the terminal console)."""
    with get_db() as db:
        apps = db.query(Application).order_by(Application.sort_order, Application.title).all()
    return jsonify([
        {"id": a.id, "title": a.title, "api_url": a.api_url}
        for a in apps
        if a.api_url
    ])


@main.route("/api/custom/commands", methods=["GET"])
def custom_commands_list():
    with get_db() as db:
        cmds = db.query(CustomCommand).order_by(CustomCommand.name).all()
    return jsonify([
        {"id": c.id, "name": c.name, "method": c.method,
         "url": c.url, "headers": c.headers, "payload": c.payload}
        for c in cmds
    ])


@main.route("/api/custom/commands", methods=["POST"])
def custom_commands_save():
    data = request.get_json()
    if not data or not data.get("name") or not data.get("url"):
        return jsonify({"error": "name and url are required"}), 400
    name    = data["name"].strip()
    url     = data["url"].strip()
    method  = (data.get("method") or "GET").upper()
    headers = data.get("headers") or ""
    payload = data.get("payload") or ""
    with get_db() as db:
        existing = db.query(CustomCommand).filter_by(name=name).first()
        if existing:
            existing.method  = method
            existing.url     = url
            existing.headers = headers
            existing.payload = payload
        else:
            db.add(CustomCommand(name=name, method=method, url=url,
                                 headers=headers, payload=payload))
    return jsonify({"status": "ok"})


@main.route("/api/custom/commands/<int:cmd_id>", methods=["DELETE"])
def custom_commands_delete(cmd_id):
    with get_db() as db:
        cmd = db.get(CustomCommand, cmd_id)
        if not cmd:
            return jsonify({"error": "not found"}), 404
        db.delete(cmd)
    return jsonify({"status": "ok"})


@main.route("/api/custom/run", methods=["POST"])
def custom_run():
    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"error": "url is required"}), 400
    url         = data["url"].strip()
    method      = (data.get("method") or "GET").upper()
    headers_raw = data.get("headers") or ""
    payload_raw = data.get("payload") or ""

    headers = {}
    if headers_raw:
        try:
            parsed = json.loads(headers_raw)
            if isinstance(parsed, dict):
                headers = parsed
        except (json.JSONDecodeError, TypeError):
            pass

    kwargs = {"headers": headers, "timeout": 10}
    if payload_raw and method in ("POST", "PUT", "PATCH", "DELETE"):
        try:
            kwargs["json"] = json.loads(payload_raw)
        except Exception:
            kwargs["data"] = payload_raw

    try:
        resp = http_requests.request(method, url, **kwargs)
        try:
            body = json.dumps(resp.json(), indent=2)
        except ValueError:
            body = resp.text
        return jsonify({
            "ok": resp.ok,
            "status": resp.status_code,
            "body": body[:4000],
            "truncated": len(body) > 4000,
        })
    except http_requests.RequestException as exc:
        return jsonify({"ok": False, "status": 0,
                        "body": f"{exc.__class__.__name__}: {exc}"})