# Copilot Memory

AIコーディングアシスタント（GitHub Copilot、Claude Code）向けのローカル長期記憶システム。

MCP（Model Context Protocol）サーバーとして動作し、過去の会話をQ&A形式で保存・検索します。全てローカルで完結し、外部APIへの通信は一切行いません。

> **本プロジェクトは [sui-memory](https://zenn.dev/noprogllama/articles/7c24b2c2410213)（Claude Code向け長期記憶エンジン）を参考に作成されています。**

## 特徴

- **完全ローカル**: 外部API不使用。埋め込みモデル（multilingual-e5-large）もローカルで実行
- **ハイブリッド検索**: FTS5キーワード検索 + ベクトル類似度検索をRRF（Reciprocal Rank Fusion）で統合
- **時間減衰**: 古い記憶ほどスコアが低下（半減期30日）
- **自動重複排除**: コサイン類似度 > 0.92 の記憶は自動的に統合
- **マルチクライアント**: GitHub Copilot と Claude Code の両方で使用可能
- **クロスプラットフォーム**: macOS / Ubuntu 対応
- **Docker対応**: コンテナでも実行可能

## アーキテクチャ

```
User → AI Assistant (Copilot/Claude) → MCP Server (stdio)
                                          ├── SQLite (FTS5 + sqlite-vec)
                                          └── Local Embedding Model
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

### Docker

```bash
# イメージのビルド
docker build -t copilot-memory .

# 動作確認
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | docker run -i --rm -v ~/.copilot-memory:/data copilot-memory
```

## プロジェクトへの展開

インストール後、各プロジェクトにメモリ指示を追加します。プロジェクトのディレクトリ内で:

```bash
# GitHub Copilot & Claude Code の両方に対応
~/.copilot-memory/venv/bin/copilot-memory init

# GitHub Copilot のみ
~/.copilot-memory/venv/bin/copilot-memory init --copilot

# Claude Code のみ
~/.copilot-memory/venv/bin/copilot-memory init --claude
```

このコマンドは以下を行います:

- `.github/copilot-instructions.md` にメモリ指示を追記（GitHub Copilot用）
- `CLAUDE.md` にメモリ指示を追記（Claude Code用）

既存のファイルがある場合は**末尾に追記**されます。ファイルがない場合は新規作成されます。2回実行しても指示が重複することはありません（マーカーで冪等性を保証）。

## エディタ設定

### GitHub Copilot（VS Code）

VS Code の `settings.json` に以下を追加:

```json
{
  "mcp": {
    "servers": {
      "copilot-memory": {
        "command": "~/.copilot-memory/venv/bin/python",
        "args": ["-m", "copilot_memory.server"]
      }
    }
  }
}
```

Docker版:

```json
{
  "mcp": {
    "servers": {
      "copilot-memory": {
        "command": "docker",
        "args": ["run", "-i", "--rm", "-v", "~/.copilot-memory:/data", "copilot-memory"]
      }
    }
  }
}
```

### Claude Code

`~/.claude/settings.json` に以下を追加:

```json
{
  "mcpServers": {
    "copilot-memory": {
      "command": "~/.copilot-memory/venv/bin/python",
      "args": ["-m", "copilot_memory.server"]
    }
  }
}
```

Docker版:

```json
{
  "mcpServers": {
    "copilot-memory": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "~/.copilot-memory:/data", "copilot-memory"]
    }
  }
}
```

## MCP ツール

### `search_memory`

過去のQ&Aペアを検索します。

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| `query` | str | (必須) | 検索クエリ |
| `limit` | int | 10 | 最大結果数 |
| `project` | str | "" | プロジェクト名でフィルタ |

### `save_memory`

Q&Aペアを保存します。

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| `question` | str | (必須) | 質問 |
| `answer` | str | (必須) | 回答の要約（2-5文） |
| `project` | str | "" | プロジェクト名 |
| `tags` | str | "" | カンマ区切りのタグ |

### `save_conversation`

複数ターンの会話を自動分割して保存します。

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| `conversation` | str | (必須) | User:/Assistant: マーカー付きの会話テキスト |
| `project` | str | "" | プロジェクト名 |

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

> **注意**: モデルを変更した場合、埋め込み次元が変わるため既存のDBは再作成が必要です。`~/.copilot-memory/memory.db` を削除してから再起動してください。

## ライセンス

MIT
