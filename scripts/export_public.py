#!/usr/bin/env python3
"""研究保管庫を読み取り、許可した川柳資料だけを公開用の静的データへ投影する。

原本・記憶・SSD設定は変更しない。相談本文は実送達済みworkshop記録と照合し、
通常会話由来の材料・個人メモ・内部識別子は出力しない。全件を検証してから書く。
--catalog-json は既存Rust catalog()から取得した公開カタログだけを指定する。
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import uuid
import zlib


MAX_JSON = 32 * 1024 * 1024
MAX_LOG = 128 * 1024 * 1024
MAX_PNG = 64 * 1024 * 1024
HASH = re.compile(r"[0-9a-f]{64}\Z")
PUBLIC_ID = re.compile(r"(?:poem|photo|material)-[0-9a-f]{16}\Z")
GAME_ID = re.compile(r"(?:minecraft:)?[a-z0-9_]+\Z")
CATALOG_ID = re.compile(r"(?:minecraft:)?[A-Za-z0-9_]+\Z")
TIMES = {"morning", "day", "evening", "night"}
ATOM_KINDS = {"catalog_label", "catalog_fact", "catalog_field", "observation", "preface_clause", "poetic_interpretation"}
CLAIM_SCOPES = {"identity_only", "source_meaning", "observed_state", "poetic_interpretation"}
REVISION_SOURCES = {"player_line_confirmed", "bookshelf_explicit", "player_revision", "player_confirmed", "workshop_revision", "workshop_accepted", "accepted_pending"}
EXCLUDED_KEYS = {"deletedPoems", "personalNotes", "favorites", "chatMaterialPoems", "dialogueAtoms", "dependentAtoms", "individualAtoms", "unsupportedAtoms", "reviewedDialogueTurns"}


class ExportError(ValueError):
    """原文やローカルの識別子を含めずに公開処理を停止する。"""


def require(condition, code):
    if not condition:
        raise ExportError(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def public_id(kind, source):
    return kind + "-" + digest(source.encode("utf-8"))[:16]


def dialogue_id(source_id, turn):
    """確認済みturnの識別子から公開IDを作る。並び順や本文の修正では変わらない。"""
    source = json.dumps([source_id, turn["workshopId"], turn["turnId"], turn["eventId"]], ensure_ascii=False, separators=(",", ":"))
    return public_id("dialogue", source)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def bootstrap_bytes(value):
    # 外部JSとしてもHTMLへ埋め込んでも、原文を実行可能なコードへ変えない。
    text = encoded(value).decode().rstrip("\n")
    for old, new in [("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")]:
        text = text.replace(old, new)
    return ("window.DOGIDO_BOOTSTRAP = " + text + ";\n").encode("utf-8")


def decode(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            require(key not in {"__proto__", "prototype", "constructor"}, "unsafe_json_key")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ExportError("invalid_json_number")))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ExportError("invalid_json") from error


def stamp(value):
    require(isinstance(value, str) and "T" in value, "invalid_timestamp")
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ExportError("invalid_timestamp") from error
    require(at.tzinfo is not None, "timestamp_requires_timezone")
    return at


def text(value, code="invalid_text"):
    require(isinstance(value, str) and bool(value.strip()), code)
    return value


def parts(relative):
    require(isinstance(relative, str) and not relative.startswith("/"), "unsafe_relative_path")
    values = relative.split("/") if relative else []
    require(all(p not in {"", ".", ".."} and "\\" not in p and "\0" not in p for p in values), "unsafe_relative_path")
    return values


class SafeRoot:
    """開いたdirectory FDを基準に読み書きし、全階層でsymlinkをたどらない。"""
    def __init__(self, path, create=False):
        self.path = Path(os.path.abspath(path))
        fd = None
        try:
            # macOSの保護対象である祖先を開いて列挙せず、明示されたrootだけを開く。
            # 祖先のlstatでもリンクを拒否し、rootの同一性を開いたFDで再照合する。
            for ancestor in reversed([self.path, *self.path.parents]):
                try:
                    info = ancestor.lstat()
                except FileNotFoundError:
                    require(create, "unsafe_or_missing_root")
                    ancestor.mkdir()
                    info = ancestor.lstat()
                require(stat.S_ISDIR(info.st_mode), "unsafe_or_missing_root")
            before = self.path.lstat()
            fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            after = os.fstat(fd)
            require((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino), "root_changed_during_open")
            self.fd = fd
        except (OSError, ExportError) as error:
            if fd is not None:
                os.close(fd)
            if isinstance(error, ExportError):
                raise
            raise ExportError("unsafe_or_missing_root") from error

    def __enter__(self):
        return self

    def __exit__(self, *_):
        os.close(self.fd)

    @contextmanager
    def directory(self, relative="", create=False):
        fd = os.dup(self.fd)
        try:
            for name in parts(relative):
                if create:
                    try:
                        os.mkdir(name, dir_fd=fd)
                    except FileExistsError:
                        pass
                new = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = new
            yield fd
        except OSError as error:
            raise ExportError("unsafe_or_missing_directory") from error
        finally:
            os.close(fd)

    def names(self, relative=""):
        with self.directory(relative) as fd:
            return sorted(os.listdir(fd))

    def exists(self, relative):
        values = parts(relative)
        with self.directory("/".join(values[:-1])) as fd:
            try:
                info = os.stat(values[-1], dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                return False
            require(not stat.S_ISLNK(info.st_mode), "symlink_not_allowed")
            return True

    def read(self, relative, limit=MAX_JSON):
        values = parts(relative)
        require(bool(values), "file_path_required")
        with self.directory("/".join(values[:-1])) as fd:
            try:
                source = os.open(values[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                with os.fdopen(source, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    require(stat.S_ISREG(info.st_mode), "regular_file_required")
                    require(info.st_size <= limit, "source_file_too_large")
                    value = stream.read(limit + 1)
                    require(len(value) <= limit, "source_file_too_large")
                    return value
            except OSError as error:
                raise ExportError("unsafe_or_missing_file") from error

    def json(self, relative, limit=MAX_JSON):
        return decode(self.read(relative, limit))

    def jsonl(self, relative):
        if not self.exists(relative):
            return []
        return [decode(line) for line in self.read(relative, MAX_LOG).splitlines() if line.strip()]

    def write(self, relative, data):
        values = parts(relative)
        with self.directory("/".join(values[:-1]), create=True) as fd:
            name = values[-1]
            try:
                old = os.stat(name, dir_fd=fd, follow_symlinks=False)
                require(stat.S_ISREG(old.st_mode), "output_must_be_regular_file")
            except FileNotFoundError:
                pass
            temporary = ".public-export-" + uuid.uuid4().hex
            try:
                target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fd)
                with os.fdopen(target, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
                os.fsync(fd)
            finally:
                try:
                    os.unlink(temporary, dir_fd=fd)
                except FileNotFoundError:
                    pass


def png_dimensions(data):
    """画素bytesを変更せず、hash検証に加えてPNGの全CRCと画素streamを検査する。"""
    require(len(data) <= MAX_PNG and data.startswith(b"\x89PNG\r\n\x1a\n"), "invalid_png")
    offset, width, height, row_bytes = 8, 0, 0, 0
    seen_header = seen_data = seen_end = False
    compressed = bytearray()
    while offset < len(data):
        require(offset + 12 <= len(data), "truncated_png")
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        require(end <= len(data), "truncated_png")
        body = data[offset + 8:offset + 8 + length]
        require(zlib.crc32(kind + body) & 0xffffffff == struct.unpack_from(">I", data, offset + 8 + length)[0], "png_crc_mismatch")
        require(kind in {b"IHDR", b"IDAT", b"IEND"}, "png_metadata_or_unsupported_chunk")
        if kind == b"IHDR":
            require(offset == 8 and not seen_header and length == 13, "invalid_png_header")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
            require(0 < width <= 16384 and 0 < height <= 16384 and width * height <= 25_000_000, "png_dimensions_out_of_bounds")
            require(depth in {8, 16} and color in {0, 2, 4, 6} and compression == filtering == interlace == 0, "unsupported_png_encoding")
            row_bytes = width * {0:1, 2:3, 4:2, 6:4}[color] * (depth // 8)
            seen_header = True
        elif kind == b"IDAT":
            require(seen_header and not seen_end, "invalid_png_order")
            compressed.extend(body)
            seen_data = True
        else:
            require(seen_data and length == 0 and end == len(data), "invalid_png_end")
            seen_end = True
        offset = end
    require(seen_end, "incomplete_png")
    expected = height * (row_bytes + 1)
    require(expected <= 256 * 1024 * 1024, "png_decoded_too_large")
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, expected + 1)
        require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(raw) == expected, "invalid_png_pixels")
        require(all(raw[n] <= 4 for n in range(0, len(raw), row_bytes + 1)), "invalid_png_filter")
    except zlib.error as error:
        raise ExportError("invalid_png_pixels") from error
    return width, height


def verse(value):
    require(isinstance(value, dict), "invalid_verse")
    lines = value.get("lines")
    require(isinstance(lines, list) and len(lines) == 3, "three_saved_lines_required")
    # 読み未確定の旧保存行は空文字のまま保つ。公開時に読みを推測しない。
    require(all(isinstance(row, dict) and isinstance(row.get("reading_text"), str) for row in lines), "missing_saved_reading")
    return {"lines": [text(row.get("surface_text"), "missing_saved_surface") for row in lines],
            "readings": [row["reading_text"] for row in lines]}


class DialogueProof:
    def __init__(self, memory):
        self.memory, self.cache = memory, {}

    def verify(self, source_id, turns):
        require(isinstance(turns, list), "invalid_dialogue_array")
        if not turns:
            return []
        if source_id.startswith("session:"):
            split = source_id.split(":", 2)
            require(len(split) == 3 and re.fullmatch(r"[A-Za-z0-9_-]+", split[1]), "invalid_session_source")
            prefix, entry = "sessions/" + split[1], split[2]
        elif source_id.startswith("root:"):
            prefix, entry = "", source_id[5:]
        else:
            raise ExportError("unsupported_poem_source")
        require(bool(entry), "missing_entry_id")
        if prefix not in self.cache:
            base = prefix + "/" if prefix else ""
            links = defaultdict(set)
            for row in self.memory.jsonl(base + "long_term/haiku_workshop_turns.jsonl"):
                require(isinstance(row, dict), "invalid_workshop_log")
                for state in [row, row.get("state_before"), row.get("state_after")]:
                    if isinstance(state, dict) and state.get("workshop_id") and state.get("entry_id"):
                        links[(row.get("session_id", ""), state["workshop_id"])].add(state["entry_id"])
            origins = defaultdict(list)
            for row in self.memory.jsonl(base + "short_term/current_session.jsonl"):
                require(isinstance(row, dict), "invalid_dialogue_log")
                if row.get("type") != "dialogue_event" or row.get("kind") != "workshop_dialogue":
                    continue
                if row.get("private") is True or row.get("workshop_record_private") is True:
                    continue
                details = row.get("details", {})
                require(isinstance(details, dict), "invalid_dialogue_details")
                if details.get("private") is True or details.get("workshop_record_private") is True:
                    continue
                origins[(row.get("workshop_id"), details.get("input_turn_id"), row.get("event_id"))].append(row)
            self.cache[prefix] = links, origins
        links, origins = self.cache[prefix]
        result, seen = [], set()
        for turn in turns:
            require(isinstance(turn, dict) and turn.get("delivery") == "confirmed", "dialogue_delivery_not_confirmed")
            key = (turn.get("workshopId"), turn.get("turnId"), turn.get("eventId"))
            require(all(isinstance(v, str) and v for v in key), "missing_dialogue_identity")
            require(key not in seen, "duplicate_public_dialogue")
            seen.add(key)
            candidates = origins.get(key, [])
            require(bool(candidates), "dialogue_origin_not_found")
            for origin in candidates:
                require(links.get((origin.get("session_id", ""), key[0])) == {entry}, "dialogue_poem_link_ambiguous_or_mismatched")
                details = origin["details"]
                require(details.get("player_text") == turn.get("player") and details.get("dogido_text") == turn.get("dogido") and origin.get("time") == turn.get("time"), "dialogue_origin_mismatch")
            stamp(turn.get("time"))
            result.append({"id": dialogue_id(source_id, turn), "time": turn["time"], "player": text(turn.get("player")), "dogido": text(turn.get("dogido")), "delivery": "confirmed"})
        return result


def project_materials(record, poem_id, counters):
    materials = record.get("materials")
    require(isinstance(materials, dict), "missing_materials")
    rows = materials.get("source_atoms", [])
    require(isinstance(rows, list), "invalid_source_atoms")
    atoms = {}
    for row in rows:
        require(isinstance(row, dict), "invalid_source_atom")
        key = text(row.get("atom_id"), "missing_atom_id")
        require(key not in atoms, "duplicate_atom_id")
        atoms[key] = row
    private, individuals, unsupported = set(), set(), set()
    for key, row in atoms.items():
        scopes = row.get("claim_scopes", [])
        require(isinstance(scopes, list) and all(isinstance(s, str) for s in scopes), "invalid_claim_scopes")
        source = row.get("source_ref", "")
        require(isinstance(source, str), "invalid_atom_source")
        if row.get("kind") == "dialogue_material" or "player_reported_context" in scopes or source.startswith("dialogue:"):
            private.add(key)
        elif source.startswith("mob_individual:"):
            individuals.add(key)
        elif row.get("kind") not in ATOM_KINDS or not re.fullmatch(r"(?:mob|block|item|biome|structure|observation|preface):[A-Za-z0-9_.:-]+", source):
            unsupported.add(key)
    chat_derived = bool(private) or bool(materials.get("player_dialogue_material"))
    counters["chatMaterialPoems"] += int(chat_derived)
    counters["dialogueAtoms"] += len(private)
    counters["individualAtoms"] += len(individuals)
    counters["unsupportedAtoms"] += len(unsupported)
    blocked = private | individuals | unsupported
    if chat_derived:
        blocked |= {key for key, row in atoms.items() if row.get("kind") in {"preface_clause", "poetic_interpretation"}}
    initial = set(blocked)
    while True:
        before = len(blocked)
        for key, row in atoms.items():
            basis = row.get("basis_atom_ids", [])
            require(isinstance(basis, list) and all(isinstance(s, str) for s in basis), "invalid_atom_dependencies")
            if any(parent in blocked or parent not in atoms for parent in basis):
                blocked.add(key)
        if len(blocked) == before:
            break
    counters["dependentAtoms"] += len(blocked - initial)
    safe = {}
    for key, row in atoms.items():
        if key in blocked:
            continue
        claim = row.get("claim_class")
        require(claim in {"factual", "interpretive"}, "invalid_claim_class")
        safe[key] = {"id": public_id("material", poem_id + ":" + key), "text": text(row.get("text")), "kind": row["kind"], "claim_class": claim,
                     "claim_scopes": [s for s in row.get("claim_scopes", []) if s in CLAIM_SCOPES]}
    line_sources = []
    original_lines = verse(record["original"])["lines"]
    for row in materials.get("line_sources", []):
        require(isinstance(row, dict) and type(row.get("line_index")) is int and 0 <= row["line_index"] <= 2, "invalid_line_source")
        ids = row.get("atom_ids", [])
        require(isinstance(ids, list) and all(isinstance(s, str) for s in ids), "invalid_line_atom_ids")
        line_sources.append({"text": original_lines[row["line_index"]], "sources": [{"text": safe[key]["text"]} for key in ids if key in safe]})
    result = {"source_atoms": list(safe.values()), "line_sources": line_sources}
    if not chat_derived and isinstance(materials.get("interpretation"), str) and materials["interpretation"].strip():
        result["interpretation"] = materials["interpretation"]
    preface = materials.get("preface_spoken") if not chat_derived else None
    return result, preface if isinstance(preface, str) and preface.strip() else None


def verify_capture(archive, directory, identity, reference):
    request = reference.get("requestId")
    require(isinstance(request, str) and request.startswith("shot_"), "invalid_capture_request")
    key = request[5:]
    try:
        require(str(uuid.UUID(key)) == key, "invalid_capture_request")
    except ValueError as error:
        raise ExportError("invalid_capture_request") from error
    bundle = directory + "/original-images/" + key
    commit = archive.json(bundle + "/commit.json")
    raw = archive.read(bundle + "/record.json")
    require(digest(raw) == commit.get("record_sha256"), "image_record_hash_mismatch")
    record = decode(raw)
    receipt = record.get("receipt", {})
    image = record.get("image", {})
    expected = reference.get("sha256")
    require(isinstance(expected, str) and HASH.fullmatch(expected), "invalid_image_hash")
    require(commit.get("schema_version") == record.get("schema_version") == 1 and commit.get("archive_id") == record.get("archive_id") == identity["archive_id"], "image_archive_identity_mismatch")
    require(record.get("poem") == identity and commit.get("capture_id") == record.get("capture_id") == request, "image_poem_identity_mismatch")
    require(receipt.get("poem_id") == identity["poem_id"] and reference.get("poemId") == identity["poem_id"], "image_poem_identity_mismatch")
    require(commit.get("sha256") == receipt.get("sha256") == image.get("sha256") == expected, "image_hash_mismatch")
    provenance = record.get("provenance", {})
    require(provenance.get("photoId") == reference.get("id") and provenance.get("poemId") == identity["poem_id"] and provenance.get("requestId") == request and provenance.get("receipt") == receipt, "image_provenance_mismatch")
    png = archive.read(bundle + "/image.png", MAX_PNG)
    require(digest(png) == expected, "image_hash_mismatch")
    width, height = png_dimensions(png)
    for owner in [commit, image, reference, provenance]:
        require(owner.get("width") == width and owner.get("height") == height, "image_dimensions_mismatch")
    require(commit.get("byte_length") == image.get("byte_length") == len(png), "image_length_mismatch")
    stamp(receipt.get("captured_at"))
    return png, receipt["captured_at"]


def load_catalog(path):
    if path is None:
        return [], {}, {}
    name = Path(os.path.abspath(path))
    with SafeRoot(name.parent) as root:
        catalog = root.json(name.name)
    validate_catalog(catalog)
    biomes, english = {}, {}
    for entry in catalog:
        if entry["category"] == "biome":
            name = entry["catalogId"].removeprefix("minecraft:")
            ident = "minecraft:" + name
            biomes[ident] = text(entry["raw"].get("label"), "missing_biome_label")
            english[ident] = entry["raw"].get("english") or name.replace("_", " ").title()
    return catalog, biomes, english


def load_exclusions(path):
    if path is None:
        return set()
    name = Path(os.path.abspath(path))
    with SafeRoot(name.parent) as root:
        manifest = root.json(name.name)
    keys(manifest, {"schemaVersion", "dialogueIds"})
    ids = manifest["dialogueIds"]
    require(manifest["schemaVersion"] == 1 and isinstance(ids, list) and all(isinstance(value, str) and re.fullmatch(r"dialogue-[0-9a-f]{16}", value) for value in ids), "invalid_reviewed_dialogue_exclusions")
    require(len(set(ids)) == len(ids), "duplicate_reviewed_dialogue_exclusion")
    return set(ids)


def build(archive_path, memory_path, catalog_path=None, exported_at=None, exclude_dialogue=None):
    """入力をすべて検証して公開JSONと画像bytesを返す。ファイル書込みは行わない。"""
    catalog, biomes, english = load_catalog(catalog_path)
    exclusions = load_exclusions(exclude_dialogue)
    verified_dialogue_ids = set()
    at = exported_at or datetime.now(timezone.utc).isoformat()
    stamp(at)
    excluded = Counter({key: 0 for key in EXCLUDED_KEYS})
    poems, images = [], {}
    photos = {"revision": 0, "items": [], "placements": {}, "originals": {}}
    with SafeRoot(archive_path) as archive, SafeRoot(memory_path) as memory:
        marker = archive.json(".dogido-research-archive.json")
        require(marker.get("schema_version") == 1 and isinstance(marker.get("archive_id"), str), "invalid_archive_marker")
        proof, seen = DialogueProof(memory), set()
        for year in archive.names():
            if not re.fullmatch(r"\d{4}", year):
                continue
            for minute in archive.names(year):
                if not re.fullmatch(r"\d{8}", minute):
                    continue
                directory = year + "/" + minute
                identity = archive.json(directory + "/identity.json")
                require(identity.get("schema_version") == 1 and identity.get("archive_id") == marker["archive_id"], "poem_archive_identity_mismatch")
                source = text(identity.get("poem_id"), "missing_poem_identity")
                require(source not in seen, "duplicate_poem_identity")
                seen.add(source)
                files = [name for name in archive.names(directory + "/snapshots") if name.endswith(".json")]
                require(len(files) == 1, "snapshot_selection_required")
                require(re.fullmatch(r"[0-9a-f]{64}\.json", files[0]), "invalid_snapshot_filename")
                raw = archive.read(directory + "/snapshots/" + files[0])
                require(digest(raw) == files[0][:-5], "snapshot_hash_mismatch")
                wrapper = decode(raw)
                require(wrapper.get("identity") == identity, "snapshot_identity_mismatch")
                record = wrapper.get("record")
                require(isinstance(record, dict) and record.get("schemaVersion") == 1 and record.get("id") == source, "snapshot_record_mismatch")
                require(type(record.get("deletedFromBookshelf")) is bool, "missing_deletion_state")
                if record["deletedFromBookshelf"]:
                    excluded["deletedPoems"] += 1
                    continue
                original, current = verse(record.get("original")), verse(record.get("current"))
                created = record["original"].get("created_at")
                born = stamp(created)
                require(born == stamp(identity.get("original_created_at")), "original_date_mismatch")
                require(born.astimezone(timezone(timedelta(hours=9))).strftime("%Y/%m%d%H%M") == directory, "poem_directory_date_mismatch")
                entry = source.split(":", 2)[2] if source.startswith("session:") and source.count(":") >= 2 else source.removeprefix("root:")
                require(record["original"].get("id") == entry, "original_entry_mismatch")
                pid = public_id("poem", source)
                dialogue = proof.verify(source, record.get("dialogue"))
                require(not verified_dialogue_ids.intersection(row["id"] for row in dialogue), "duplicate_public_dialogue_identity")
                verified_dialogue_ids.update(row["id"] for row in dialogue)
                excluded["reviewedDialogueTurns"] += sum(row["id"] in exclusions for row in dialogue)
                dialogue = [row for row in dialogue if row["id"] not in exclusions]
                history = []
                for revision in record.get("revisions", []):
                    require(revision.get("haiku_id") == entry, "revision_poem_mismatch")
                    saved = verse(revision)
                    stamp(revision.get("created_at"))
                    row = {"date": revision["created_at"], **saved}
                    if revision.get("source") in REVISION_SOURCES:
                        row["source"] = revision["source"]
                    history.append(row)
                materials, preface = project_materials(record, pid, excluded)
                world = record["original"].get("world", {})
                biome = world.get("biome")
                biome = (biome if biome.startswith("minecraft:") else "minecraft:" + biome) if isinstance(biome, str) and GAME_ID.fullmatch(biome) else None
                period = world.get("time_phase") if world.get("time_phase") in TIMES else None
                require(record["original"].get("author") in {"dogido", "player"}, "unsupported_author_kind")
                poem = {"id": pid, "kind": "poem", "createdAt": created, "date": born.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"),
                        "author": "ドギド" if record["original"]["author"] == "dogido" else "プレイヤー", "biomeId": biome, "timeOfDay": period,
                        "lines": current["lines"], "originalLines": original["lines"], "original": original, "current": current, "history": history,
                        "materials": materials, "dialogue": dialogue, "revised": bool(history), "preface": preface}
                poems.append(poem)
                note = record.get("player", {})
                excluded["personalNotes"] += bool(note.get("note"))
                excluded["favorites"] += note.get("favorite") is True
                source_photos = record.get("photos", {})
                refs = source_photos.get("references", [])
                require(isinstance(refs, list), "invalid_photo_references")
                photo_ids = {}
                for ref in refs:
                    require(isinstance(ref, dict) and ref.get("source") == "minecraft", "unsupported_photo_source")
                    raw_id = text(ref.get("id"), "missing_photo_identity")
                    require(raw_id not in photo_ids, "duplicate_photo_identity")
                    png, captured = verify_capture(archive, directory, identity, ref)
                    sha = digest(png)
                    target = "data/images/" + sha + ".png"
                    images[target] = png
                    photo = public_id("photo", source + ":" + raw_id)
                    photo_ids[raw_id] = photo
                    photos["items"].append({"id": photo, "filename": "image-" + sha[:16] + ".png", "title": "発句時の景色", "width": ref["width"], "height": ref["height"],
                                            "source": "minecraft", "sha256": sha, "poemId": pid, "url": target, "createdAt": captured, "protected": True})
                slots = source_photos.get("slots", [])
                require(isinstance(slots, list) and len(slots) <= 3, "invalid_photo_slots")
                require(all(value is None or value in photo_ids for value in slots), "unverified_photo_slot")
                if slots:
                    photos["placements"]["poems:" + pid] = [photo_ids.get(value) for value in slots]
                original_photo = source_photos.get("originalId")
                if original_photo is not None:
                    require(original_photo in photo_ids, "unverified_original_photo")
                    photos["originals"]["poems:" + pid] = photo_ids[original_photo]
    require(exclusions <= verified_dialogue_ids, "reviewed_dialogue_exclusion_not_found")
    poems.sort(key=lambda p: (p["createdAt"], p["id"]), reverse=True)
    photos["items"].sort(key=lambda p: p["id"])
    data = {"schemaVersion": 1, "exportedAt": at,
            "publication": {"poems": len(poems), "revisions": sum(len(p["history"]) for p in poems), "workshopTurns": sum(len(p["dialogue"]) for p in poems), "images": len(photos["items"]), "excluded": dict(excluded)},
            "poems": poems, "catalog": catalog, "biomes": biomes, "biomeEnglish": english,
            "player": {"poems": {}, "catalog": {}}, "status": {"readOnly": True}, "photos": photos}
    validate_data(data, images)
    return data, images


def keys(value, required, optional=()):
    require(isinstance(value, dict) and set(required) <= value.keys() and value.keys() <= set(required) | set(optional), "public_schema_keys_mismatch")


def validate_catalog(catalog):
    require(isinstance(catalog, list), "invalid_public_catalog")
    seen = set()
    for entry in catalog:
        keys(entry, {"id", "category", "catalogId", "raw"})
        require(entry["category"] in {"biome", "structure", "mob", "block", "item"}, "invalid_public_catalog_category")
        require(isinstance(entry["catalogId"], str) and CATALOG_ID.fullmatch(entry["catalogId"]), "invalid_public_catalog_id")
        require(entry["id"] == entry["category"] + ":" + entry["catalogId"] and entry["id"] not in seen and isinstance(entry["raw"], dict), "invalid_public_catalog_entry")
        seen.add(entry["id"])


def validate_public_verse(row):
    keys(row, {"lines", "readings"})
    for field in ["lines", "readings"]:
        require(isinstance(row[field], list) and len(row[field]) == 3 and all(isinstance(s, str) and (field == "readings" or s.strip()) for s in row[field]), "invalid_public_verse")


def validate_data(data, images):
    """CIでも呼べる公開形式の検査。未知キー・生の参照・画像外のパスは受理しない。"""
    keys(data, {"schemaVersion", "exportedAt", "publication", "poems", "catalog", "biomes", "biomeEnglish", "player", "status", "photos"})
    require(data["schemaVersion"] == 1 and data["status"] == {"readOnly": True} and data["player"] == {"poems": {}, "catalog": {}}, "invalid_public_contract")
    stamp(data["exportedAt"])
    validate_catalog(data["catalog"])
    for field in ["biomes", "biomeEnglish"]:
        require(isinstance(data[field], dict) and all(isinstance(k, str) and k.startswith("minecraft:") and GAME_ID.fullmatch(k) and isinstance(v, str) for k, v in data[field].items()), "invalid_biome_map")
    require(isinstance(data["poems"], list), "invalid_public_poems")
    poem_ids, dialogue_ids = set(), set()
    for poem in data["poems"]:
        keys(poem, {"id", "kind", "createdAt", "date", "author", "biomeId", "timeOfDay", "lines", "originalLines", "original", "current", "history", "materials", "dialogue", "revised", "preface"})
        require(isinstance(poem["id"], str) and re.fullmatch(r"poem-[0-9a-f]{16}", poem["id"]) and poem["id"] not in poem_ids, "invalid_public_poem_id")
        poem_ids.add(poem["id"])
        require(poem["kind"] == "poem" and poem["author"] in {"ドギド", "プレイヤー"}, "invalid_public_poem_kind")
        at = stamp(poem["createdAt"])
        require(poem["date"] == at.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d"), "invalid_public_poem_date")
        require(poem["biomeId"] is None or isinstance(poem["biomeId"], str) and GAME_ID.fullmatch(poem["biomeId"]), "invalid_public_biome")
        require(poem["timeOfDay"] is None or poem["timeOfDay"] in TIMES, "invalid_public_time_phase")
        validate_public_verse(poem["original"])
        validate_public_verse(poem["current"])
        require(poem["lines"] == poem["current"]["lines"] and poem["originalLines"] == poem["original"]["lines"], "public_verse_mismatch")
        require(isinstance(poem["history"], list) and poem["revised"] is bool(poem["history"]), "invalid_public_revisions")
        for row in poem["history"]:
            keys(row, {"date", "lines", "readings"}, {"source"})
            stamp(row["date"])
            validate_public_verse({"lines": row["lines"], "readings": row["readings"]})
            require("source" not in row or row["source"] in REVISION_SOURCES, "invalid_public_revision_source")
        keys(poem["materials"], {"source_atoms", "line_sources"}, {"interpretation"})
        require(isinstance(poem["materials"]["source_atoms"], list) and isinstance(poem["materials"]["line_sources"], list), "invalid_public_materials")
        for atom in poem["materials"]["source_atoms"]:
            keys(atom, {"id", "text", "kind", "claim_class", "claim_scopes"})
            require(isinstance(atom["id"], str) and re.fullmatch(r"material-[0-9a-f]{16}", atom["id"]) and atom["kind"] in ATOM_KINDS and atom["claim_class"] in {"factual", "interpretive"}, "invalid_public_atom")
            text(atom["text"])
            require(isinstance(atom["claim_scopes"], list) and all(s in CLAIM_SCOPES for s in atom["claim_scopes"]), "invalid_public_claim_scope")
        for row in poem["materials"]["line_sources"]:
            keys(row, {"text", "sources"})
            require(row["text"] in poem["originalLines"] and isinstance(row["sources"], list), "invalid_public_line_source")
            for source in row["sources"]:
                keys(source, {"text"})
                require(source["text"] in [a["text"] for a in poem["materials"]["source_atoms"]], "unpublished_line_source")
        if "interpretation" in poem["materials"]:
            text(poem["materials"]["interpretation"])
        require(poem["preface"] is None or isinstance(poem["preface"], str), "invalid_public_preface")
        require(isinstance(poem["dialogue"], list), "invalid_public_dialogue")
        for row in poem["dialogue"]:
            keys(row, {"id", "time", "player", "dogido", "delivery"})
            require(isinstance(row["id"], str) and re.fullmatch(r"dialogue-[0-9a-f]{16}", row["id"]) and row["id"] not in dialogue_ids and row["delivery"] == "confirmed", "invalid_public_dialogue_identity")
            dialogue_ids.add(row["id"])
            stamp(row["time"])
            text(row["player"])
            text(row["dogido"])
    photos = data["photos"]
    keys(photos, {"revision", "items", "placements", "originals"})
    require(photos["revision"] == 0 and isinstance(photos["items"], list) and isinstance(photos["placements"], dict) and isinstance(photos["originals"], dict), "invalid_public_photos")
    photo_ids, image_paths = {}, set()
    for item in photos["items"]:
        keys(item, {"id", "filename", "title", "width", "height", "source", "sha256", "poemId", "url", "createdAt", "protected"})
        require(isinstance(item["id"], str) and re.fullmatch(r"photo-[0-9a-f]{16}", item["id"]) and item["id"] not in photo_ids, "invalid_public_photo_id")
        require(item["poemId"] in poem_ids and item["source"] == "minecraft" and item["protected"] is True and item["title"] == "発句時の景色", "invalid_public_photo_metadata")
        sha = item["sha256"]
        require(isinstance(sha, str) and HASH.fullmatch(sha) and item["filename"] == "image-" + sha[:16] + ".png" and item["url"] == "data/images/" + sha + ".png", "invalid_public_image_path")
        stamp(item["createdAt"])
        require(item["url"] in images and digest(images[item["url"]]) == sha, "public_image_hash_mismatch")
        require(png_dimensions(images[item["url"]]) == (item["width"], item["height"]), "public_image_dimensions_mismatch")
        photo_ids[item["id"]] = item["poemId"]
        image_paths.add(item["url"])
    require(set(images) == image_paths, "unexpected_public_image")
    for target, slots in photos["placements"].items():
        require(target.startswith("poems:") and target[6:] in poem_ids and isinstance(slots, list) and len(slots) <= 3, "invalid_public_photo_placement")
        require(all(slot is None or photo_ids.get(slot) == target[6:] for slot in slots), "mismatched_public_photo_placement")
    for target, photo in photos["originals"].items():
        require(target.startswith("poems:") and target[6:] in poem_ids and photo_ids.get(photo) == target[6:], "invalid_public_original_photo")
    publication = data["publication"]
    keys(publication, {"poems", "revisions", "workshopTurns", "images", "excluded"})
    require(publication["poems"] == len(data["poems"]) and publication["revisions"] == sum(len(p["history"]) for p in data["poems"]) and publication["workshopTurns"] == sum(len(p["dialogue"]) for p in data["poems"]) and publication["images"] == len(photos["items"]), "public_counts_mismatch")
    keys(publication["excluded"], EXCLUDED_KEYS)
    require(all(type(n) is int and n >= 0 for n in publication["excluded"].values()), "invalid_excluded_counts")


def data_files(root):
    if not root.exists("data"):
        return set()
    result = set()
    for name in root.names("data"):
        if name == "images":
            for image in root.names("data/images"):
                root.read("data/images/" + image, MAX_PNG)
                result.add("data/images/" + image)
        else:
            root.read("data/" + name)
            result.add("data/" + name)
    return result


def validate_site(output):
    """外部サービスや元の私有記憶を使わず、公開ディレクトリだけをCIで検査する。"""
    with SafeRoot(output) as root:
        data = root.json("data/research.json")
        images = {}
        for photo in data.get("photos", {}).get("items", []):
            path = photo.get("url")
            require(isinstance(path, str) and re.fullmatch(r"data/images/[0-9a-f]{64}\.png", path), "invalid_public_image_path")
            images[path] = root.read(path, MAX_PNG)
        validate_data(data, images)
        require(root.read("bootstrap.js") == bootstrap_bytes(data), "bootstrap_data_mismatch")
        require(data_files(root) == {"data/research.json"} | set(images), "unexpected_public_data_file")
        return data["publication"]


def export(archive, memory, output, catalog_json=None, exported_at=None, exclude_dialogue=None):
    destination = Path(os.path.abspath(output))
    for source in [archive, memory]:
        require(not destination.is_relative_to(Path(os.path.abspath(source))), "output_inside_private_source")
    data, images = build(archive, memory, catalog_json, exported_at, exclude_dialogue)
    expected = {"data/research.json"} | set(images)
    with SafeRoot(destination, create=True) as root:
        # 前回の画像が残って公開されることを防ぐ。未知の既存資料は自動削除しない。
        require(data_files(root) <= expected, "stale_or_unexpected_public_data_use_fresh_output")
        for relative, contents in sorted(images.items()):
            root.write(relative, contents)
        root.write("data/research.json", encoded(data))
        root.write("bootstrap.js", bootstrap_bytes(data))
    validate_site(destination)
    return data["publication"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--memory", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--catalog-json", type=Path)
    parser.add_argument("--exported-at")
    parser.add_argument("--exclude-dialogue", type=Path, help="本文を人が確認して除外を決めた公開dialogue IDのmanifest")
    parser.add_argument("--validate-site", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.validate_site:
            require(not any([args.archive, args.memory, args.output, args.catalog_json, args.exported_at, args.exclude_dialogue]), "validation_does_not_accept_source_arguments")
            result = validate_site(args.validate_site)
        else:
            require(all([args.archive, args.memory, args.output]), "archive_memory_output_required")
            result = export(args.archive, args.memory, args.output, args.catalog_json, args.exported_at, args.exclude_dialogue)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ExportError, KeyError, TypeError, ValueError) as error:
        # 不正レコードの本文・ID・パスをCIログへ流さない。
        code = str(error) if isinstance(error, ExportError) else "invalid_source_structure"
        print("Export stopped: " + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
