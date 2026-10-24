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

追加の静的画像 `site/assets/dogido_2026-10-22_09.35.09.png` も目視確認しました。Minecraftの風景とキャラクターが写る854×480の画像で、通常対話・個人情報の表示や追加メタデータはありません。原ファイルを同じ場所・同じbytesで保持し、`docs/image-review.json` にpath・SHA-256・寸法を登録しています。配布検査はその確認記録との一致を必須にします。句との対応は登録しておらず、研究データの写真12枚の件数には含めません。

川柳相談自体は公開対象です。この分類は「本人の発話を一切含まない」という意味ではありません。通常対話から公開本文を推測・生成することはせず、相談と記録された原文を使います。

## 更新

Python 3とNode.jsを使います。必要な公開カタログは本体の既存 `bookshelf::store::catalog()` から取得します。別のカタログ解析器や本体のHTTPサーバーは追加しません。

```sh
# 本体のコードを更新したときは、本体側で先にビルドする。
./dogido-rust/cargo.sh build --locked --lib
```

公開リポジトリ側で、元の保存先を引数として指定します。元データは読み取りだけです。先に本体の本棚で研究保存先が「保全済み」になっていることを確認します。書き出し先は毎回新しく作り、消えた画像を前回分から持ち越さないようにします。

```sh
mkdir -p .preview
python3 -B scripts/export_catalog.py --upstream ../DokiDoki-Dogido --output .preview/catalog.json
record_export_dir=$(mktemp -d .preview/records-XXXXXX)
python3 -B scripts/export_public.py --archive /path/to/research-archive --memory /path/to/runtime-memory --catalog-json .preview/catalog.json --exclude-dialogue docs/publication-exclusions.json --output "$record_export_dir"
python3 -B scripts/export_public.py --validate-site "$record_export_dir"
```

新規・変更分の相談本文と画像を確認し、必要な除外IDと `docs/image-review.json` を更新します。確認後、候補の `data/` 一式と `bootstrap.js` で `site/data/` と `site/bootstrap.js` を置き換えて、次を実行します。古い画像との追加・結合はしません。

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.test.cjs
python3 -B scripts/check_site.py
```

差分をレビューしてからコミット・pushします。`docs/publication-exclusions.json` は本文を含まない公開用IDの除外記録です。初回確認で見つかった相談終了後の通常対話1往復を除いています。元アーカイブや通常対話ログをこのリポジトリへ置かないでください。

`main` へのpushで検証が走り、成功した `site/` だけをGitHub Pagesへ公開します。CIに私有アーカイブや対話ログを渡しません。CIは公開済み投影と合成テストで公開境界を検査します。

## 複数の保存版からの更新

2026-10-24に、同じ句の保存snapshotが増えた場合の更新に対応しました。CLIの引数は同じです。

- `--memory` 配下の `bookshelf/state.json` にある既存の `researchSnapshots` から、本体が最後に保全した版を選びます。`researchStorage` が同じarchive IDで `ready`、句ID・SHA-256・保存先が一致することを確認し、実ファイルの内容hashとidentityも照合します。更新時刻やhashの辞書順では新旧を判定しません。
- 原句・現在句・推敲履歴・相談・材料・写真は、その選択版だけを使います。過去の保存版を混ぜず、最新の選択版で消えた相談・写真や削除句を復活させません。公開する相談の元ログ照合と、通常対話・私的情報の除外は維持します。同じ相談IDに通常対話または非公開の元ログが重複していれば停止します。
- 除外IDは、相談や句が削除されてもmanifestに残します。選択版にないIDは、hashと句の同一性を確認した旧版で存在だけを検査します。その本文は公開に使いません。未知ID・重複IDは引き続きエラーです。`publication.excluded.reviewedDialogueTurns` は今回の選択版で実際に除いた往復数で、manifestの全ID数より小さくなることがあります。
- 同じアーカイブの台帳がある場合は、未保全、参照先の欠損、句の不足、書き出し中の台帳変更で出力前に停止します。別archive IDの台帳がある場合も停止します。台帳のない旧コピーは各句が一版だけなら読めます。複数版で台帳がない場合は `snapshot_selection_required` となるため、元記録を削らず、本体の保全完了と対応する `--memory` を確認します。

合成データによるPythonテスト50件、Nodeテスト6件と、現在の公開データのサイト整合検査を確認済みです。SSD上の最新記録を公開し直したことを示す検査ではありません。

追加の静的画像を含む配布検査では、Python52件・Node6件とサイト41ファイルの整合検査が成功しました。未確認画像や画像の差替えを止める検査も維持しています。

## UIの出所

本体の `tools/dogido-library/` を基にしています。表紙・カラム・見開き・写真表示を継承し、編集、削除、復元、保存先設定、個人メモ、ローカルAPIを除いています。元ファイルのhashは `upstream-ui.json` に記録しています。

利用者はブラウザーで記録を読むことができます。実際にドギドを動かす場合は、本棚の「ドギドを試す」から本体の導入説明を参照してください。このサイトでMinecraftやモデルを動かす機能はありません。

## 初回の確認

106句、推敲25件、川柳相談282往復、画像12枚を収録しました。Pythonの公開境界テスト31件、Nodeの表示テスト4件、配布ファイル37件の整合検査が通っています。ブラウザーで表紙、句集の検索、原句と編集後の句、推敲履歴、相談記録、フォトブック、あんちょこのカテゴリ表示を確認しました。狭い画面でも句と履歴を読めることを確認しています。
