# 川柳研究データの公開（2026-10-24）

`Dogido_Research` は、本体の本棚を閲覧専用にしたGitHub Pagesサイトです。元の記憶と研究アーカイブは私有のまま、許可した項目から公開用データを組み立てます。本体やSSDの設定を変更する処理、定期的な自動push、外部から自宅サーバーへ接続する処理はありません。

## 公開範囲

| 対象 | 扱い |
|---|---|
| 原句・現在句・推敲履歴 | 保存された表記と読みを公開。品質による選別や書換えはしない |
| 川柳の相談・講評 | 実配送済みの `workshop_dialogue` と、句への一意な対応、本文の一致を照合して公開 |
| 通常対話・私的メモ・本人のしおり | 公開しない |
| 発句材料 | 許可した観測・カタログ材料だけを投影。通常対話由来の要約・モチーフ・派生材料は除外 |
| 会話由来材料を使った句の見どころ・解釈 | 間接的な混入を避けるため公開しない。句本文と川柳相談本文は保持 |
| 写真 | 確認した原画像を同じbytesでコピー。元ファイル名、保存パス、receipt、provenanceは公開しない |
| 識別子 | 公開用の句・写真IDに置換。session/workshop/turn/個体の生IDは公開しない |
| ごみ箱の句 | 公開しない |
| モデル内部状態の数値 | 採取未実装のため未収録。空フォルダを収録済みデータとして見せない |

画像12枚は目視確認済み。うち4枚にはMinecraftのバイオーム・ゲーム内座標・句のHUD表示があり、8枚はHUDのない身体視点の画像です。通常の会話表示や実名等は確認されませんでした。PNGにテキスト・EXIFなどの追加メタデータはありません。

川柳相談自体は公開対象です。この分類は「本人の発話を一切含まない」という意味ではありません。通常対話から公開本文を推測・生成することはせず、相談と記録された原文を使います。

## 更新

Python 3とNode.jsを使います。必要な公開カタログは本体の既存 `bookshelf::store::catalog()` から取得します。別のカタログ解析器や本体のHTTPサーバーは追加しません。

```sh
# 本体のコードを更新したときは、本体側で先にビルドする。
./dogido-rust/cargo.sh build --locked --lib
```

公開リポジトリ側で、元の保存先を引数として指定します。元データは読み取りだけです。

```sh
python3 -B scripts/export_catalog.py --upstream ../DokiDoki-Dogido --output .preview/catalog.json
python3 -B scripts/export_public.py --archive /path/to/research-archive --memory /path/to/runtime-memory --catalog-json .preview/catalog.json --exclude-dialogue docs/publication-exclusions.json --output site
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.test.cjs
python3 -B scripts/check_site.py
```

新しい画像と公開本文を確認し、`docs/image-review.json` の確認記録を更新して、差分をレビューしてからコミット・pushします。`docs/publication-exclusions.json` は本文を含まない公開用IDの除外記録です。初回確認で見つかった相談終了後の通常対話1往復を除いています。元アーカイブや通常対話ログをこのリポジトリへ置かないでください。複数の保存snapshotがある場合は、書き出し処理が指定・選別を求めることがあります。hashの辞書順を新旧の判定には使いません。

`main` へのpushで検証が走り、成功した `site/` だけをGitHub Pagesへ公開します。CIに私有アーカイブや対話ログを渡しません。CIは公開済み投影と合成テストで公開境界を検査します。

## UIの出所

本体の `tools/dogido-library/` を基にしています。表紙・カラム・見開き・写真表示を継承し、編集、削除、復元、保存先設定、個人メモ、ローカルAPIを除いています。元ファイルのhashは `upstream-ui.json` に記録しています。

利用者はブラウザーで記録を読むことができます。実際にドギドを動かす場合は、本棚の「ドギドを試す」から本体の導入説明を参照してください。このサイトでMinecraftやモデルを動かす機能はありません。

## 初回の確認

106句、推敲25件、川柳相談282往復、画像12枚を収録しました。Pythonの公開境界テスト31件、Nodeの表示テスト4件、配布ファイル37件の整合検査が通っています。ブラウザーで表紙、句集の検索、原句と編集後の句、推敲履歴、相談記録、フォトブック、あんちょこのカテゴリ表示を確認しました。狭い画面でも句と履歴を読めることを確認しています。
