from __future__ import annotations

import json
import urllib.error
import urllib.request
from importlib.resources import files


def _gapi(base, token, path, method="GET", body=None):
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req) as r:
        ct = r.headers.get("Content-Type", "")
        raw = r.read()
        return json.loads(raw.decode("utf-8")) if "application/json" in ct else None


def _find_prom_uid(base, token):
    dss = _gapi(base, token, "/api/datasources") or []
    for ds in dss:
        if ds.get("type") == "prometheus" and "grafana.net" in (ds.get("url") or ""):
            return ds["uid"]
    for ds in dss:
        if ds.get("type") == "prometheus":
            return ds["uid"]
    raise RuntimeError("No Prometheus datasource found in Grafana Cloud")


def _ensure_folder(base, token, title):
    for f in _gapi(base, token, "/api/folders") or []:
        if f.get("title") == title:
            return f
    return _gapi(base, token, "/api/folders", method="POST", body={"title": title})


def _patch_ds(d, prom_uid):
    ds = {"type": "prometheus", "uid": prom_uid}
    dd = json.loads(json.dumps(d))  # deep copy
    dd["datasource"] = ds
    for p in dd.get("panels", []) or []:
        p["datasource"] = ds
        for t in p.get("targets", []) or []:
            t["datasource"] = ds
        for sp in p.get("panels", []) or []:
            sp["datasource"] = ds
            for t in sp.get("targets", []) or []:
                t["datasource"] = ds
    templ = (dd.get("templating") or {}).get("list") or []
    for v in templ:
        v["datasource"] = ds
        if v.get("includeAll"):
            v["allValue"] = ".*"
        v.setdefault("refresh", 2)
    return dd


def push_dashboards_from_pkg(
    base_url: str, token: str, folder_title: str = "Service Infrastructure"
):
    prom_uid = _find_prom_uid(base_url, token)
    folder = _ensure_folder(base_url, token, folder_title)
    fuid = folder["uid"]

    # packaged dashboards live in providers/grafana/dashboards/*.json
    dash_root = files("svc_infra.obs.providers.grafana").joinpath("dashboards")
    for res in dash_root.iterdir():
        if not res.name.endswith(".json"):
            continue
        d = json.loads(res.read_text(encoding="utf-8"))
        d = _patch_ds(d, prom_uid)
        d.setdefault("title", res.name[:-5])
        payload = {
            "dashboard": d,
            "folderUid": fuid,
            "overwrite": True,
            "message": "svc-infra auto-sync",
        }
        _gapi(base_url, token, "/api/dashboards/db", method="POST", body=payload)
