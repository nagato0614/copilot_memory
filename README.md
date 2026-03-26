# Copilot Memory

AIコーディングアシスタント（GitHub Copilot、Claude Code）向けのローカル長期記憶システム。

MCP（Model Context Protocol）サーバーとして動作し、会話・作業記録・設計決定・知見などをQ&A形式で保存・検索します。全てローカルで完結し、外部APIへの通信は一切行いません。

> **本プロジェクトは [sui-memory](https://zenn.dev/noprogllama/articles/7c24b2c2410213)（Claude Code向け長期記憶エンジン）を参考に作成されています。**

## 特徴

- **完全ローカル**: 外部API不使用。埋め込みモデル（multilingual-e5-large）もローカルで実行
- **ハイブリッド検索**: FTS5キーワード検索 + ベクトル類似度検索をRRF（Reciprocal Rank Fusion）で統合
- **時間減衰**: 古い記憶ほどスコアが低下（半減期30日）
- **自動重複排除**: コサイン類似度 > 0.92 の記憶は自動的に統合
- **マルチクライアント**: GitHub Copilot と Claude Code の両方で使用可能
- **Claude Code自動化**: Stopフックで自動保存 + UserPromptSubmitフックで自動検索
- **エディタ設定の自動化**: `init` コマンドでVS Code / Claude Code の設定を自動書き込み
- **クロスプラットフォーム**: macOS / Ubuntu 対応
- **Docker対応**: コンテナでも実行可能

## アーキテクチャ

```
User → AI Assistant (Copilot/Claude) → MCP Server (stdio)
                                          ├── SQLite (FTS5 + sqlite-vec)
                                          └── Local Embedding Model (multilingual-e5-large)
```

## インストール

### 前提条件

- Python >= 3.10
- SQLite >= 3.34.0（FTS5 trigram tokenizer に必要）

### ワンライナー（リポジトリのクローン不要）

```bash
curl -fsSL https://raw.githubusercontent.com/nagato0614/copilot_memory/main/install.sh | bash
```

### リポジトリからインストール

```bash
git clone https://github.com/nagato0614/copilot_memory.git
cd copilot_memory
./install.sh
```

`install.sh` が以下を自動実行します:

1. Python バージョン確認
2. `~/.copilot-memory/` に仮想環境を作成
3. パッケージをインストール
4. 埋め込みモデルをダウンロード（初回のみ、約2.2GB）
5. SQLite データベースを初期化
6. **VS Code / Claude Code の設定ファイルを自動更新**（MCP接続 + フック設定）

### Docker

```bash
docker build -t copilot-memory .

echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | docker run -i --rm -v ~/.copilot-memory:/data copilot-memory
```

## プロジェクトへの展開

インストール後、各プロジェクトにメモリ指示を追加します。プロジェクトのディレクトリ内で:

```bash
# GitHub Copilot & Claude Code の両方に対応（エディタ設定も自動更新）
~/.copilot-memory/venv/bin/copilot-memory init

# GitHub Copilot のみ
~/.copilot-memory/venv/bin/copilot-memory init --copilot

# Claude Code のみ
~/.copilot-memory/venv/bin/copilot-memory init --claude

# プロンプト追記のみ（エディタ設定は触らない）
~/.copilot-memory/venv/bin/copilot-memory init --no-editor
```

このコマンドは以下を行います:

- `.github/copilot-instructions.md` にメモリ指示を追記（GitHub Copilot用）
- `CLAUDE.md` にメモリ指示を追記（Claude Code用）
- VS Code `settings.json` に MCP サーバー設定を追加
- Claude Code `~/.claude/settings.json` に MCP サーバー + UserPromptSubmit/Stop フック設定を追加

既存のファイルがある場合は**マージ・追記**されます。2回実行しても設定が重複することはありません。変更前にバックアップが作成されます。

## Claude Code フック（自動検索 + 自動保存）

Claude Codeでは2つのフックで検索・保存を完全自動化します:

| フック | タイミング | 動作 |
|---|---|---|
| `UserPromptSubmit` | ユーザーが入力確定 | メモリを検索し、関連コンテキストをClaudeに自動注入 |
| `Stop` | Claude応答完了 | 最後のやり取りを自動保存 |

- LLMに`search_memory`/`save_memory`を呼ばせる必要がない（確実に動作）
- `install.sh` または `copilot-memory init --claude` で自動設定
- ログ: `~/.copilot-memory/hook.log`

### GitHub Copilot

GitHub Copilotにはフック機能がないため、MCPツール + プロンプト指示で対応します。
`copilot-instructions.md` のプロンプトで`search_memory`/`save_memory`の呼び出しを指示します。

## MCP ツール

### `search_memory`

過去の記憶を検索します。

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| `query` | str | (必須) | 検索クエリ |
| `limit` | int | 10 | 最大結果数 |
| `project` | str | "" | プロジェクト名でフィルタ |

### `save_memory`

記憶を保存します。設計決定・作業記録・知見・議論など何でも保存できます。

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| `content` | str | (必須) | 自然言語テキスト（2-5文、具体的に） |
| `project` | str | "" | プロジェクト名 |
| `tags` | str | "" | カンマ区切りのタグ |

### `save_conversation`

複数ターンの会話を自動分割して保存します。

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| `conversation` | str | (必須) | User:/Assistant: マーカー付きの会話テキスト |
| `project` | str | "" | プロジェクト名 |

## CLI コマンド

| コマンド | 説明 |
|---|---|
| `copilot-memory` | MCPサーバーを起動（デフォルト） |
| `copilot-memory serve` | MCPサーバーを明示的に起動 |
| `copilot-memory init` | プロジェクトにプロンプト追記 + エディタ設定 |
| `copilot-memory hook-save` | Claude Code Stopフックハンドラ（内部用） |
| `copilot-memory hook-search` | Claude Code UserPromptSubmitフックハンドラ（内部用） |
| `copilot-memory ingest <path>` | ファイル/ディレクトリをメモリに登録 |
| `copilot-memory ingest --list` | 登録済みファイル一覧 |
| `copilot-memory ingest --remove <path>` | 登録済みファイルを削除 |
| `copilot-memory search <query>` | ターミナルからメモリを検索 |
| `copilot-memory stats` | DB統計を表示 |
| `copilot-memory uninstall` | `~/.copilot-memory/` を削除 |

## ファイル登録（ingest）

プロジェクトのドキュメントやソースコードを事前にメモリに登録できます。登録した内容は `search_memory` で会話メモリと一緒に検索されます。

```bash
# ファイル単体を登録
copilot-memory ingest path/to/design.md

# ディレクトリを再帰的に登録
copilot-memory ingest docs/

# 特定の拡張子のみ
copilot-memory ingest src/ --ext .cpp,.java,.py

# 登録済みファイル一覧
copilot-memory ingest --list
```

### 対応ファイル形式

| 形式 | 拡張子 | 分割方法 |
|---|---|---|
| Markdown | `.md` | 見出し単位 |
| AsciiDoc | `.adoc` | 見出し単位 |
| PlantUML | `.puml` | ファイル全体 |
| Python | `.py` | def/class 単位 |
| C/C++ | `.c`, `.cpp`, `.h`, `.hpp` | 関数単位 |
| Java | `.java` | メソッド/クラス単位 |
| Rust | `.rs` | fn/impl 単位 |
| Dart | `.dart` | class/関数単位 |
| Go | `.go` | func/type 単位 |
| TypeScript/JS | `.ts`, `.tsx`, `.js`, `.jsx` | export/function/class 単位 |
| Swift | `.swift` | func/class/struct 単位 |
| Kotlin | `.kt` | fun/class/object 単位 |
| Docker Compose | `compose.yml` | ファイル全体 |
| その他 | `.txt`, `.json`, `.yaml` 等 | 固定長分割 |

`.gitignore` のパターンを自動的に尊重します。

同じファイルを再実行すると、古いチャンクは自動で削除されて再登録されます。

## 技術詳細

- **埋め込みモデル**: `intfloat/multilingual-e5-large`（1024次元、100+言語対応、高精度）
- **ベクトルDB**: SQLite + [sqlite-vec](https://github.com/asg017/sqlite-vec)
- **キーワード検索**: SQLite FTS5（trigram tokenizer）
- **検索統合**: RRF（Reciprocal Rank Fusion、k=60）
- **時間減衰**: 半減期30日
- **DB場所**: `~/.copilot-memory/memory.db`

## 環境変数

| 変数 | デフォルト | 説明 |
|---|---|---|
| `COPILOT_MEMORY_DIR` | `~/.copilot-memory` | データディレクトリ |
| `COPILOT_MEMORY_MODEL` | `intfloat/multilingual-e5-large` | 埋め込みモデル名 |

> **注意**: v0.2.0 はv0.1.x と DB互換性がありません。アップグレード時は `~/.copilot-memory/memory.db` を削除してください。
> モデルを変更した場合も同様にDBの再作成が必要です。

## ライセンス

MIT
