#!/usr/bin/env python3
"""公開siteだけを検証し、原本・通常対話・未確認画像の配布を止める。

公開形式・画像hash・bootstrap一致はexport_publicと共有する。ここでは配布ファイルの
許可範囲、表示資産、画像の目視確認記録、明示除外を検査し、通信や書込みはしない。
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from export_public import ExportError, digest, require, validate_site


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []
        self.scripts = []
        self.metadata = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for key in ("src", "href"):
            if values.get(key):
                self.references.append(values[key])
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        if tag == "meta":
            self.metadata[values.get("property") or values.get("name")] = values.get("content")


def check(root: Path) -> dict:
    root = root.resolve(strict=True)
    site = root / "site"
    result = validate_site(site)
    data = json.loads((site / "data/research.json").read_text(encoding="utf-8"))
    provenance = json.loads((root / "upstream-ui.json").read_text(encoding="utf-8"))
    expected = set(provenance["files"])
    expected |= {p.removeprefix("site/") for p in provenance["newFiles"] if p.startswith("site/")}
    expected |= {"bootstrap.js", "data/research.json"}
    expected |= {p["url"] for p in data["photos"]["items"]}
    found = set()
    for path in site.rglob("*"):
        require(not path.is_symlink(), "site_symlink_not_allowed")
        if path.is_file():
            found.add(path.relative_to(site).as_posix())
    require(found == expected, "site_file_allowlist_mismatch")
    for name, checksum in provenance["files"].items():
        if name not in provenance["adaptedFiles"]:
            require(digest((site / name).read_bytes()) == checksum, "upstream_visual_asset_changed")

    reviews = json.loads((root / "docs/image-review.json").read_text(encoding="utf-8"))
    approved = {r["sha256"] for r in reviews["images"] if r.get("review") == "approved_for_initial_publication"}
    require(all(item["sha256"] in approved for item in data["photos"]["items"]), "image_visual_review_required")
    exclusions = json.loads((root / "docs/publication-exclusions.json").read_text(encoding="utf-8"))
    excluded = set(exclusions["dialogueIds"])
    published = {turn["id"] for poem in data["poems"] for turn in poem["dialogue"]}
    require(not published & excluded, "reviewed_private_dialogue_was_published")
    require(result["excluded"]["reviewedDialogueTurns"] == len(excluded), "reviewed_exclusion_count_mismatch")

    page = References()
    html = (site / "index.html").read_text(encoding="utf-8")
    page.feed(html)
    for value in page.references:
        url = urlsplit(value)
        if url.scheme or url.netloc:
            require((url.scheme == "https" and url.netloc == "github.com") or value in {
                "https://x.com/intent/tweet", "https://www.instagram.com/"
            }, "unexpected_external_page_link")
            continue
        if not url.path:
            continue
        require(not url.path.startswith("/") and ".." not in Path(url.path).parts, "nonrelative_site_link")
        require((site / url.path).is_file(), "broken_site_link")
    require("connect-src 'none'" in html and "form-action 'none'" in html, "readonly_browser_policy_missing")
    # 共有プレビューは利用者が指定したフライヤーだけ。原画像のbytesとカードURLを照合する。
    share_review = json.loads((root / "docs/share-image-review.json").read_text(encoding="utf-8"))
    require(share_review["path"] == "assets/dogido-flyer.jpg", "unexpected_share_image")
    flyer = (site / share_review["path"]).read_bytes()
    require(digest(flyer) == share_review["sha256"], "share_image_review_mismatch")
    public_url = "https://yukincom.github.io/Dogido_Research/"
    require(page.metadata.get("og:url") == public_url, "unexpected_share_url")
    require(all(page.metadata.get(key) == public_url + share_review["path"] for key in ("og:image", "twitter:image")), "share_preview_image_mismatch")
    for script in page.scripts:
        if script == "bootstrap.js":
            continue
        body = (site / script).read_text(encoding="utf-8")
        require(not re.search(r"fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|/api/|X-Dogido|webkit|setInterval\s*\(", body), "local_or_remote_runtime_connection")
    # データは分類器で伏字にせず、混入時に公開を止めて書出し元を確認する。
    for filename in ("bootstrap.js", "data/research.json"):
        body = (site / filename).read_text(encoding="utf-8")
        require(not re.search(r"(?:/Users/|/Volumes/|/private/|file://|localhost|127\.0\.0\.1|[A-Za-z]:\\\\)", body), "private_location_in_public_data")
        require(not re.search(r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b", body), "raw_uuid_in_public_data")
    return {**result, "siteFiles": len(found), "loadedScripts": len(page.scripts)}


if __name__ == "__main__":
    try:
        print(json.dumps(check(Path(__file__).resolve().parents[1]), ensure_ascii=False, sort_keys=True))
    except (ExportError, KeyError, ValueError) as error:
        print("Site check failed: " + (str(error) if isinstance(error, ExportError) else "invalid_publication_files"), file=sys.stderr)
        raise SystemExit(1)
