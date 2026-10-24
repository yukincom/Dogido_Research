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
        review["images"] = []
        path.write_text(json.dumps(review))
        with self.assertRaisesRegex(ExportError, "image_visual_review_required"):
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

    def test_shared_file_cannot_differ_from_preview(self):
        path = self.root / "site/share-image.js"
        source = path.read_text()
        path.write_text(source.replace('"base64":"', '"base64":"AAAA', 1))
        with self.assertRaisesRegex(ExportError, "share_image_bundle_mismatch"):
            check(self.root)


if __name__ == "__main__":
    unittest.main()
