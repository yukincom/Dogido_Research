#!/usr/bin/env python3
"""本体のコンパイル済みcatalog()を読み、公開カタログだけを書き出す。

記憶や設定を開かず、既存Rust投影をそのまま使う。出力の更新だけを担当し、
本体ビルド・サービス起動・Git操作・依存のインストールは行わない。
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def export_catalog(upstream: Path, output: Path, rustc: str | None = None) -> int:
    upstream = upstream.resolve(strict=True)
    deps = upstream / "dogido-rust/target/debug/deps"
    libraries = sorted(deps.glob("libdogido_rust-*.rlib"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not libraries:
        raise ValueError("先に本体で ./dogido-rust/cargo.sh build --locked --lib を実行してください。")
    compiler = rustc or shutil.which("rustc")
    if not compiler:
        candidates = sorted((upstream / ".dogido_tools/rust/rustup/toolchains").glob("*/bin/rustc"))
        if len(candidates) != 1:
            raise ValueError("利用する本体と同じRustコンパイラを --rustc で指定してください。")
        compiler = str(candidates[0])
    source = '''fn main() {
    let entries = dogido_rust::bookshelf::store::catalog();
    print!("[");
    for (index, entry) in entries.iter().enumerate() {
        if index > 0 { print!(","); }
        print!("{entry}");
    }
    println!("]");
}'''
    with tempfile.TemporaryDirectory(prefix="dogido-catalog-") as directory:
        root = Path(directory)
        script = root / "export_catalog.rs"
        executable = root / ("export_catalog.exe" if os.name == "nt" else "export_catalog")
        script.write_text(source, encoding="utf-8")
        subprocess.run([
            compiler, "--edition=2024", "--crate-name", "dogido_public_catalog",
            str(script), "-L", f"dependency={deps}", "--extern",
            f"dogido_rust={libraries[0]}", "-o", str(executable),
        ], check=True)
        entries = json.loads(subprocess.check_output([str(executable)], text=True))
    if not isinstance(entries, list) or not entries:
        raise ValueError("本体から公開カタログを取得できませんでした。")
    if any(not isinstance(row, dict) or set(row) != {"id", "category", "catalogId", "raw"} for row in entries):
        raise ValueError("本体のカタログ形式が変わりました。公開仕様を確認してください。")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ValueError("出力先のシンボリックリンクは使用できません。")
    output.write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return len(entries)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rustc")
    args = parser.parse_args()
    print(json.dumps({"catalogEntries": export_catalog(args.upstream, args.output, args.rustc)}))


if __name__ == "__main__":
    main()
