"""公開境界の試験。実際の会話・句・画像はfixtureへコピーしない。"""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
from contextlib import redirect_stderr

MODULE = Path(__file__).resolve().parents[1] / "scripts/export_public.py"
spec = importlib.util.spec_from_file_location("export_public", MODULE)
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)

SECRET = "PRIVATE_CHAT_SENTINEL_原文を公開しない"
AT = "2026-10-24T00:00:00Z"
ARCHIVE_ID = "11111111-1111-4111-8111-111111111111"
CAPTURE_ID = "22222222-2222-4222-8222-222222222222"


def chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)


def png(extra=b""):
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 6, 0, 0, 0)) + extra + chunk(b"IDAT", zlib.compress(b"\0" + b"\x20\x30\x40\xff" * 2)) + chunk(b"IEND", b"")


def atom(identifier, body, kind="observation", source="observation:time_phase", basis=()):
    return {"atom_id": identifier, "text": body, "kind": kind, "source_ref": source, "claim_class": "factual",
            "claim_scopes": ["player_reported_context" if kind == "dialogue_material" else "observed_state"], "basis_atom_ids": list(basis)}


class Fixture:
    def __init__(self, root):
        self.root = root
        self.archive, self.memory, self.output = root / "archive", root / "memory", root / "site"
        self.folder = self.archive / "2026/10240900"
        self.snapshots = self.folder / "snapshots"
        self.bundle = self.folder / "original-images" / CAPTURE_ID
        self.long = self.memory / "sessions/s/long_term"
        self.short = self.memory / "sessions/s/short_term"
        for path in [self.snapshots, self.bundle, self.long, self.short]:
            path.mkdir(parents=True)
        self.identity = {"schema_version": 1, "archive_id": ARCHIVE_ID, "poem_id": "session:s:haiku-one", "original_created_at": AT}
        self.write_json(self.archive / ".dogido-research-archive.json", {"schema_version": 1, "archive_id": ARCHIVE_ID, "volume_uuid": None})
        self.write_json(self.folder / "identity.json", self.identity)
        self.public_atom = atom("weather", "朝の森")
        self.private_atom = atom("private", SECRET, "dialogue_material", "dialogue:private-turn")
        self.materials = {"source_atoms": [self.public_atom, self.private_atom, atom("derived", SECRET + " derived", "catalog_fact", "item:stone", ["private"]), atom("derived2", SECRET + " transitive", "catalog_fact", "item:stone", ["derived"])],
                          "player_dialogue_material": {"summary": SECRET, "motifs": [SECRET], "source_turn_ids": ["private-turn"]},
                          "interpretation": SECRET, "preface_spoken": SECRET,
                          "line_sources": [{"line_index": 0, "text": SECRET, "atom_ids": ["weather", "private"], "sources": [{"text": SECRET}]}]}
        lines = [{"surface_text": value, "reading_text": reading, "source_atoms": [self.private_atom], "source_atom_ids": ["private"], "provenance": SECRET}
                 for value, reading in [("朝の森", "あさのもり"), ("葉の影ゆれる", "はのかげゆれる"), ("鳥の声", "とりのこえ")]]
        original = {"id": "haiku-one", "author": "dogido", "created_at": AT, "lines": lines, "materials_snapshot": copy.deepcopy(self.materials), "interpretation": SECRET,
                    "world": {"biome": "forest", "time_phase": "morning", "player_uuid": SECRET, "coordinates": SECRET}, "session_id": SECRET}
        self.dialogue = {"time": AT, "workshopId": "workshop-private-id", "turnId": "turn-private-id", "eventId": "event-private-id", "player": "上の句はどういう意味？", "dogido": "朝の森を見た時の句やで。", "delivery": "confirmed"}
        self.origin = {"type": "dialogue_event", "kind": "workshop_dialogue", "time": AT, "session_id": "s", "session_instance": "instance-private-id", "workshop_id": self.dialogue["workshopId"], "event_id": self.dialogue["eventId"],
                       "details": {"input_turn_id": self.dialogue["turnId"], "player_text": self.dialogue["player"], "dogido_text": self.dialogue["dogido"]}}
        self.workshop = {"session_id": "s", "state_before": {"workshop_id": self.dialogue["workshopId"], "entry_id": "haiku-one"}, "input": SECRET}
        self.record = {"schemaVersion": 1, "id": self.identity["poem_id"], "deletedFromBookshelf": False, "original": original, "current": copy.deepcopy(original), "revisions": [],
                       "materials": self.materials, "dialogue": [self.dialogue], "player": {"favorite": True, "note": SECRET}, "unknown_private": SECRET,
                       "photos": {"references": [], "slots": [], "originalId": None}}
        self.write_logs()
        self.set_image(png())

    @staticmethod
    def write_json(path, value):
        path.write_bytes(public.encoded(value))

    def write_logs(self, extra_links=()):
        (self.long / "haiku_workshop_turns.jsonl").write_bytes(public.encoded(self.workshop) + b"".join(public.encoded(r) for r in extra_links))
        ordinary = {"type": "dialogue_event", "kind": "player_chat", "text": SECRET, "details": {"player_text": SECRET, "dogido_text": SECRET}}
        (self.short / "current_session.jsonl").write_bytes(public.encoded(ordinary) + public.encoded(self.origin))

    def snapshot(self):
        for old in self.snapshots.glob("*.json"):
            old.unlink()
        raw = public.encoded({"identity": self.identity, "record": self.record})
        path = self.snapshots / (public.digest(raw) + ".json")
        path.write_bytes(raw)
        return path

    def set_image(self, contents):
        sha = public.digest(contents)
        ref = {"id": "photo-private-id", "filename": SECRET + ".png", "title": SECRET, "width": 2, "height": 1, "source": "minecraft", "sha256": sha,
               "poemId": self.identity["poem_id"], "requestId": "shot_" + CAPTURE_ID, "unknown": SECRET}
        receipt = {"poem_id": self.identity["poem_id"], "sha256": sha, "directory": "/Users/private/" + SECRET, "filename": SECRET + ".png", "session_id": SECRET, "captured_at": AT,
                   "capture_view": {"owner_uuid": SECRET, "body_entity_uuid": SECRET, "body_epoch": SECRET}}
        provenance = {"photoId": ref["id"], "poemId": ref["poemId"], "requestId": ref["requestId"], "receipt": receipt, "originalPoem": copy.deepcopy(self.record["original"]), "width": 2, "height": 1, "private": SECRET}
        record = {"schema_version": 1, "archive_id": ARCHIVE_ID, "poem": self.identity, "capture_id": ref["requestId"], "receipt": receipt, "provenance": provenance,
                  "image": {"sha256": sha, "byte_length": len(contents), "width": 2, "height": 1}}
        raw = public.encoded(record)
        (self.bundle / "record.json").write_bytes(raw)
        (self.bundle / "image.png").write_bytes(contents)
        self.write_json(self.bundle / "commit.json", {"schema_version": 1, "archive_id": ARCHIVE_ID, "capture_id": ref["requestId"], "sha256": sha, "record_sha256": public.digest(raw), "byte_length": len(contents), "width": 2, "height": 1})
        self.record["photos"] = {"references": [ref], "slots": [ref["id"], None, None], "originalId": ref["id"]}
        self.snapshot()

    def build(self):
        return public.build(self.archive, self.memory, exported_at=AT)

    def export(self):
        return public.export(self.archive, self.memory, self.output, exported_at=AT)


class PublicExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dogido-public-test-", dir="/private/tmp" if Path("/private/tmp").is_dir() else None)
        self.f = Fixture(Path(self.temporary.name))

    def tearDown(self):
        self.temporary.cleanup()

    def assert_stopped(self, code, work=None):
        with self.assertRaisesRegex(public.ExportError, code):
            (work or self.f.build)()

    def test_private_fields_and_transitive_conversation_materials_never_escape(self):
        data, images = self.f.build()
        serialized = public.encoded(data).decode()
        self.assertNotIn(SECRET, serialized)
        for forbidden in ["session:s:haiku-one", ARCHIVE_ID, CAPTURE_ID, "workshop-private-id", "turn-private-id", "event-private-id", "photo-private-id", "source_ref", "source_turn_ids", "materials_snapshot", "capture_view", "owner_uuid", "receipt", "provenance"]:
            self.assertNotIn(forbidden, serialized)
        poem = data["poems"][0]
        self.assertEqual([a["text"] for a in poem["materials"]["source_atoms"]], ["朝の森"])
        self.assertEqual(poem["materials"]["line_sources"], [{"text": "朝の森", "sources": [{"text": "朝の森"}]}])
        self.assertIsNone(poem["preface"])
        self.assertNotIn("interpretation", poem["materials"])
        self.assertEqual(data["publication"]["excluded"]["dependentAtoms"], 2)
        self.assertEqual(data["publication"]["excluded"]["personalNotes"], 1)
        self.assertEqual(data["publication"]["excluded"]["chatMaterialPoems"], 1)
        self.assertEqual(next(iter(images.values())), png())

    def test_poem_and_verified_workshop_words_are_preserved_exactly(self):
        self.f.record["original"]["lines"][0]["surface_text"] = "  朝の森 <script> </script> & \u2028  "
        self.f.record["current"] = copy.deepcopy(self.f.record["original"])
        self.f.dialogue["player"] = self.f.origin["details"]["player_text"] = "  これ、どういう意味なん？\nそのまま聞きたい。  "
        self.f.write_logs()
        self.f.snapshot()
        self.f.export()
        with public.SafeRoot(self.f.output) as root:
            data = root.json("data/research.json")
            boot = root.read("bootstrap.js").decode()
        self.assertEqual(data["poems"][0]["originalLines"][0], self.f.record["original"]["lines"][0]["surface_text"])
        self.assertEqual(data["poems"][0]["dialogue"][0]["player"], self.f.dialogue["player"])
        self.assertNotIn("<script>", boot)
        self.assertEqual(public.validate_site(self.f.output)["workshopTurns"], 1)

    def test_dialogue_must_match_origin_text(self):
        self.f.dialogue["player"] = "保存後に改変した本文"
        self.f.snapshot()
        self.assert_stopped("dialogue_origin_mismatch")

    def test_unrelated_or_ordinary_origin_cannot_authorize_workshop_export(self):
        for kind in ["player_chat", "unrelated", "knowledge"]:
            with self.subTest(kind=kind):
                self.f.origin["kind"] = kind
                self.f.write_logs()
                self.assert_stopped("dialogue_origin_not_found")

    def test_private_flag_and_unconfirmed_delivery_are_rejected(self):
        self.f.origin["workshop_record_private"] = True
        self.f.write_logs()
        self.assert_stopped("dialogue_origin_not_found")
        self.f.origin.pop("workshop_record_private")
        self.f.write_logs()
        self.f.dialogue["delivery"] = "pending"
        self.f.snapshot()
        self.assert_stopped("dialogue_delivery_not_confirmed")

    def test_ambiguous_or_wrong_poem_link_is_rejected(self):
        extra = {"session_id": "s", "state_after": {"workshop_id": self.f.dialogue["workshopId"], "entry_id": "different-poem"}}
        self.f.write_logs([extra])
        self.assert_stopped("dialogue_poem_link_ambiguous_or_mismatched")
        self.f.workshop["state_before"]["entry_id"] = "different-poem"
        self.f.write_logs()
        self.assert_stopped("dialogue_poem_link_ambiguous_or_mismatched")

    def test_missing_proof_rejects_whole_export_before_any_write(self):
        (self.f.short / "current_session.jsonl").unlink()
        self.assert_stopped("dialogue_origin_not_found", self.f.export)
        self.assertFalse(self.f.output.exists())

    def test_duplicate_turns_are_not_silently_published(self):
        self.f.record["dialogue"].append(copy.deepcopy(self.f.dialogue))
        self.f.snapshot()
        self.assert_stopped("duplicate_public_dialogue")

    def test_unknown_and_individual_atoms_are_excluded(self):
        self.f.materials["source_atoms"].extend([atom("named", SECRET, "catalog_label", "mob_individual:" + CAPTURE_ID), atom("new", SECRET, "future_unknown_kind", "observation:new")])
        self.f.snapshot()
        data, _ = self.f.build()
        self.assertNotIn(SECRET, public.encoded(data).decode())
        self.assertEqual(data["publication"]["excluded"]["individualAtoms"], 1)
        self.assertEqual(data["publication"]["excluded"]["unsupportedAtoms"], 1)

    def test_revision_projection_preserves_lines_but_omits_free_metadata(self):
        revision = {"id": SECRET, "haiku_id": "haiku-one", "created_at": "2026-10-24T00:01:00Z", "lines": copy.deepcopy(self.f.record["original"]["lines"]),
                    "source": "player_line_confirmed", "comment": SECRET, "evidence": SECRET, "edits": [{"replacement_text": SECRET}], "parent_revision_id": SECRET}
        revision["lines"][1]["surface_text"] = "風が通る道"
        revision["lines"][1]["reading_text"] = "かぜがとおるみち"
        self.f.record["revisions"] = [revision]
        self.f.record["current"] = revision
        self.f.snapshot()
        data, _ = self.f.build()
        history = data["poems"][0]["history"]
        self.assertEqual(history[0]["lines"][1], "風が通る道")
        self.assertEqual(history[0]["source"], "player_line_confirmed")
        self.assertNotIn(SECRET, public.encoded(data).decode())

    def test_saved_unknown_reading_stays_empty_instead_of_being_invented(self):
        self.f.record["original"]["lines"][0]["reading_text"] = ""
        self.f.record["current"]["lines"][0]["reading_text"] = ""
        self.f.snapshot()
        data, _ = self.f.build()
        self.assertEqual(data["poems"][0]["original"]["readings"][0], "")
        self.assertEqual(data["poems"][0]["current"]["readings"][0], "")

    def test_reviewed_exclusion_uses_stable_identity_and_preserves_other_bodies(self):
        excluded = public.dialogue_id(self.f.record["id"], self.f.dialogue)
        manifest = self.f.root / "reviewed-exclusions.json"
        self.f.write_json(manifest, {"schemaVersion": 1, "dialogueIds": [excluded]})
        other = copy.deepcopy(self.f.dialogue)
        other.update({"turnId": "earlier-turn", "eventId": "earlier-event", "player": "この一句について聞きたい。", "dogido": "一緒に見てみよか。"})
        self.f.record["dialogue"].insert(0, other)
        origin = copy.deepcopy(self.f.origin)
        origin["event_id"] = other["eventId"]
        origin["details"].update({"input_turn_id": other["turnId"], "player_text": other["player"], "dogido_text": other["dogido"]})
        with (self.f.short / "current_session.jsonl").open("ab") as stream:
            stream.write(public.encoded(origin))
        self.f.snapshot()
        data, _ = public.build(self.f.archive, self.f.memory, exported_at=AT, exclude_dialogue=manifest)
        actual = data["poems"][0]["dialogue"]
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["player"], other["player"])
        self.assertEqual(actual[0]["dogido"], other["dogido"])
        self.assertEqual(actual[0]["id"], public.dialogue_id(self.f.record["id"], other))
        self.assertNotIn(excluded, public.encoded(data).decode())
        self.assertEqual(data["publication"]["excluded"]["reviewedDialogueTurns"], 1)
        self.assertEqual(data["publication"]["workshopTurns"], 1)

    def test_unknown_or_duplicate_reviewed_exclusions_stop_before_writing(self):
        manifest = self.f.root / "reviewed-exclusions.json"
        self.f.write_json(manifest, {"schemaVersion": 1, "dialogueIds": ["dialogue-" + "a" * 16]})
        self.assert_stopped("reviewed_dialogue_exclusion_not_found", lambda: public.export(self.f.archive, self.f.memory, self.f.output, exported_at=AT, exclude_dialogue=manifest))
        self.assertFalse(self.f.output.exists())
        value = public.dialogue_id(self.f.record["id"], self.f.dialogue)
        self.f.write_json(manifest, {"schemaVersion": 1, "dialogueIds": [value, value]})
        self.assert_stopped("duplicate_reviewed_dialogue_exclusion", lambda: public.build(self.f.archive, self.f.memory, exported_at=AT, exclude_dialogue=manifest))

    def test_deleted_poems_are_not_public(self):
        self.f.record["deletedFromBookshelf"] = True
        self.f.snapshot()
        data, images = self.f.build()
        self.assertEqual(data["poems"], [])
        self.assertEqual(images, {})
        self.assertEqual(data["publication"]["excluded"]["deletedPoems"], 1)

    def test_snapshot_hash_and_identity_are_verified(self):
        path = self.f.snapshot()
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_stopped("snapshot_hash_mismatch")
        self.f.identity["poem_id"] = "session:s:another"
        self.f.snapshot()
        self.assert_stopped("snapshot_identity_mismatch")

    def test_multiple_snapshots_require_explicit_selection(self):
        first = self.f.snapshot()
        second = first.read_bytes() + b" "
        (self.f.snapshots / (public.digest(second) + ".json")).write_bytes(second)
        self.assert_stopped("snapshot_selection_required")

    def test_image_hash_and_bundle_record_hash_are_verified(self):
        (self.f.bundle / "image.png").write_bytes(png() + b"changed")
        self.assert_stopped("image_hash_mismatch")
        self.f.set_image(png())
        raw = (self.f.bundle / "record.json").read_bytes()
        (self.f.bundle / "record.json").write_bytes(raw + b" ")
        self.assert_stopped("image_record_hash_mismatch")

    def test_png_text_metadata_and_crc_corruption_are_rejected_without_editing(self):
        self.f.set_image(png(chunk(b"tEXt", b"Comment\0" + SECRET.encode())))
        self.assert_stopped("png_metadata_or_unsupported_chunk")
        broken = bytearray(png())
        broken[-1] ^= 1
        self.f.set_image(bytes(broken))
        self.assert_stopped("png_crc_mismatch")

    def test_source_symlinks_cannot_escape_the_archive(self):
        snapshot = self.f.snapshot()
        outside = self.f.root / "outside.json"
        outside.write_bytes(snapshot.read_bytes())
        snapshot.unlink()
        snapshot.symlink_to(outside)
        self.assert_stopped("unsafe_or_missing_file")
        linked = self.f.root / "linked-archive"
        linked.symlink_to(self.f.archive, target_is_directory=True)
        self.assert_stopped("unsafe_or_missing_root", lambda: public.build(linked, self.f.memory, exported_at=AT))

    def test_output_symlink_is_rejected_and_outside_files_are_untouched(self):
        outside = self.f.root / "outside"
        outside.mkdir()
        sentinel = outside / "sentinel"
        sentinel.write_text(SECRET)
        (self.f.output / "data").mkdir(parents=True)
        (self.f.output / "data/images").symlink_to(outside, target_is_directory=True)
        self.assert_stopped("unsafe_or_missing_directory", self.f.export)
        self.assertEqual(sentinel.read_text(), SECRET)
        self.assertEqual(list(outside.iterdir()), [sentinel])

    def test_output_inside_private_inputs_is_forbidden(self):
        for source in [self.f.archive, self.f.memory]:
            with self.subTest(source=source.name):
                self.assert_stopped("output_inside_private_source", lambda: public.export(self.f.archive, self.f.memory, source / "public", exported_at=AT))
                self.assertFalse((source / "public").exists())

    def test_unknown_old_generated_files_block_refresh_instead_of_publishing_them(self):
        self.f.export()
        stale = self.f.output / "data/private.json"
        stale.write_text(SECRET)
        before = (self.f.output / "data/research.json").read_bytes()
        self.assert_stopped("stale_or_unexpected_public_data", self.f.export)
        self.assertEqual((self.f.output / "data/research.json").read_bytes(), before)
        self.assert_stopped("unexpected_public_data_file", lambda: public.validate_site(self.f.output))

    def test_offline_validator_rejects_unknown_keys_paths_and_bootstrap_changes(self):
        data, images = self.f.build()
        mutated = copy.deepcopy(data)
        mutated["poems"][0]["current"]["private_note"] = SECRET
        self.assert_stopped("public_schema_keys_mismatch", lambda: public.validate_data(mutated, images))
        mutated = copy.deepcopy(data)
        mutated["photos"]["items"][0]["url"] = "../../private.png"
        self.assert_stopped("invalid_public_image_path", lambda: public.validate_data(mutated, images))
        self.f.export()
        (self.f.output / "bootstrap.js").write_text("window.DOGIDO_BOOTSTRAP = {};\n")
        self.assert_stopped("bootstrap_data_mismatch", lambda: public.validate_site(self.f.output))

    def test_exports_are_deterministic_and_inputs_remain_byte_identical(self):
        def fingerprint(root):
            return {str(p.relative_to(root)): public.digest(p.read_bytes()) for p in root.rglob("*") if p.is_file()}
        before = [fingerprint(p) for p in [self.f.archive, self.f.memory]]
        first = self.f.export()
        output = fingerprint(self.f.output)
        second = self.f.export()
        self.assertEqual(first, second)
        self.assertEqual(fingerprint(self.f.output), output)
        self.assertEqual([fingerprint(p) for p in [self.f.archive, self.f.memory]], before)

    def test_public_catalog_is_supplied_without_reimplementing_its_content(self):
        catalog = [{"id": "biome:forest", "category": "biome", "catalogId": "forest", "raw": {"label": "森林", "english": "Forest", "note": "公開カタログの説明"}},
                   {"id": "structure:Witch_hut", "category": "structure", "catalogId": "Witch_hut", "raw": {"label": "魔女の小屋"}}]
        path = self.f.root / "catalog.json"
        self.f.write_json(path, catalog)
        data, _ = public.build(self.f.archive, self.f.memory, path, AT)
        self.assertEqual(data["catalog"], catalog)
        self.assertEqual(data["biomes"], {"minecraft:forest": "森林"})
        self.assertEqual(data["biomeEnglish"], {"minecraft:forest": "Forest"})

    def test_cli_error_never_prints_private_input_text(self):
        self.f.dialogue["player"] = SECRET
        self.f.snapshot()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = public.main(["--archive", str(self.f.archive), "--memory", str(self.f.memory), "--output", str(self.f.output), "--exported-at", AT])
        self.assertEqual(code, 2)
        self.assertNotIn(SECRET, stderr.getvalue())
        self.assertIn("dialogue_origin_mismatch", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
