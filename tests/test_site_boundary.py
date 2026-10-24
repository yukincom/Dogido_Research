"""配布直前のファイル混入・未確認画像・除外済み会話の再流入を検査する。"""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_site import check
from export_public import ExportError, bootstrap_bytes, encoded


class SiteBoundary(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dogido-public-site-")
        self.root = Path(self.temporary.name).resolve()
        for name in ("site", "docs"):
            shutil.copytree(ROOT / name, self.root / name)
        shutil.copyfile(ROOT / "upstream-ui.json", self.root / "upstream-ui.json")

    def tearDown(self):
        self.temporary.cleanup()

    def data(self):
        return json.loads((self.root / "site/data/research.json").read_text())

    def write_data(self, data):
        (self.root / "site/data/research.json").write_bytes(encoded(data))
        (self.root / "site/bootstrap.js").write_bytes(bootstrap_bytes(data))

    def test_extra_private_file_cannot_be_distributed(self):
        (self.root / "site/private.json").write_text('{"private":"SYNTHETIC_PRIVATE_TEXT"}')
        with self.assertRaisesRegex(ExportError, "site_file_allowlist_mismatch"):
            check(self.root)

    def test_new_images_need_visual_review(self):
        path = self.root / "docs/image-review.json"
        review = json.loads(path.read_text())
        review["images"] = [row for row in review["images"] if "path" in row]
        path.write_text(json.dumps(review))
        with self.assertRaisesRegex(ExportError, "image_visual_review_required"):
            check(self.root)

    def test_inactive_exclusions_remain_valid_and_out_of_published_dialogue(self):
        data = self.data()
        data["publication"]["excluded"]["reviewedDialogueTurns"] = 0
        self.write_data(data)
        self.assertEqual(check(self.root)["excluded"]["reviewedDialogueTurns"], 0)

    def test_registered_static_image_cannot_be_replaced_without_review(self):
        path = self.root / "site/assets/dogido_2026-10-22_09.35.09.png"
        path.write_bytes(path.read_bytes() + b"unreviewed-change")
        with self.assertRaisesRegex(ExportError, "asset_image_review_mismatch"):
            check(self.root)

    def test_static_image_needs_explicit_visual_approval(self):
        path = self.root / "docs/image-review.json"
        review = json.loads(path.read_text())
        for row in review["images"]:
            if row.get("path") == "assets/dogido_2026-10-22_09.35.09.png":
                row["review"] = "pending"
        path.write_text(json.dumps(review))
        with self.assertRaisesRegex(ExportError, "asset_visual_review_required"):
            check(self.root)

    def test_exclusion_count_cannot_exceed_the_manifest(self):
        data = self.data()
        exclusions = json.loads((self.root / "docs/publication-exclusions.json").read_text())
        data["publication"]["excluded"]["reviewedDialogueTurns"] = len(exclusions["dialogueIds"]) + 1
        self.write_data(data)
        with self.assertRaisesRegex(ExportError, "reviewed_exclusion_count_mismatch"):
            check(self.root)

    def test_excluded_dialogue_cannot_return(self):
        data = self.data()
        excluded = json.loads((self.root / "docs/publication-exclusions.json").read_text())["dialogueIds"][0]
        data["poems"][0]["dialogue"].append({"id": excluded, "time": data["poems"][0]["createdAt"], "player": "SYNTHETIC_PRIVATE_TEXT", "dogido": "SYNTHETIC_REPLY", "delivery": "confirmed"})
        data["publication"]["workshopTurns"] += 1
        self.write_data(data)
        with self.assertRaisesRegex(ExportError, "reviewed_private_dialogue_was_published"):
            check(self.root)

    def test_local_path_in_allowed_text_stops_publication(self):
        data = self.data()
        data["poems"][0]["preface"] = "/Users/example/private-research"
        self.write_data(data)
        with self.assertRaisesRegex(ExportError, "private_location_in_public_data"):
            check(self.root)

    def test_retained_visual_assets_match_upstream(self):
        path = self.root / "site/styles.css"
        path.write_text(path.read_text() + "\n/* unexpected */\n")
        with self.assertRaisesRegex(ExportError, "upstream_visual_asset_changed"):
            check(self.root)

    def test_unreviewed_share_image_cannot_be_published(self):
        (self.root / "site/assets/dogido-flyer.jpg").write_bytes(b"unreviewed")
        with self.assertRaisesRegex(ExportError, "share_image_review_mismatch"):
            check(self.root)

    def test_share_card_cannot_use_a_different_image(self):
        path = self.root / "site/index.html"
        source = path.read_text()
        path.write_text(source.replace('name="twitter:image" content="https://yukincom.github.io/Dogido_Research/assets/dogido-flyer.jpg"', 'name="twitter:image" content="https://example.com/other.jpg"'))
        with self.assertRaisesRegex(ExportError, "share_preview_image_mismatch"):
            check(self.root)


if __name__ == "__main__":
    unittest.main()
