# Memory System Instructions

MANDATORY: You have access to a long-term memory system via MCP tools (`copilot-memory` server).
You MUST follow these rules for EVERY interaction without exception.

Note: Memory search is automatically injected via hook. Memory save is also backed up via hook.
However, you SHOULD still call both tools explicitly for best results.

## BEFORE every response:
1. Call `search_memory` with the user's message as the query if relevant context is needed.
2. If relevant memories are found, incorporate them into your response naturally.
3. Do not mention the memory system to the user unless asked.

## AFTER every response:
You MUST call `save_memory` **multiple times** — one call per distinct topic, fact, or action.
Do NOT bundle everything into a single save. Split into focused, granular memories.

## Parameters:
- `content`: Natural language text (2-5 sentences). Include file paths, commands, code snippets, version numbers, error messages, reasoning, trade-offs. Must be understandable on its own by a third party.
- `project`: The current workspace/project name
- `tags`: Relevant topic tags (e.g., "python,fastapi,auth")

## What to save — ALL of the following:

| Category | Example `content` |
|---|---|
| Design decision | "FastAPIの認証方式にJWTを採用した。python-joseライブラリを使用し、app/auth/jwt.pyにcreate_access_token()を実装。SECRET_KEYは環境変数JWT_SECRETから取得、アルゴリズムはHS256、有効期限30分。セッション方式はRedis依存が増えるため不採用とした。" |
| Implementation | "app/auth/jwt.pyにJWTトークン生成を実装した。jose.jwt.encode()でペイロード{sub: user_id, exp: datetime}をエンコード。OAuth2PasswordBearerでtokenUrl='auth/login'を設定し、Depends(get_current_user)でエンドポイントに認証を注入するパターンを採用。" |
| Work log | "認証機能の実装で以下のファイルを変更した。新規作成: app/auth/jwt.py, app/auth/deps.py, app/models/user.py, app/routers/auth.py。変更: app/main.py (ルーター追加), requirements.txt (python-jose, passlib追加)。" |
| Bug fix | "hook.pyの_extract_last_turn()にQ&Aペアリングバグがあった。最後のuserとassistantを独立追跡していたため異なるターンが組み合わされていた。ペアベース追跡に変更し修正。" |
| Insight | "sqlite-vecのパフォーマンス特性: WALモード+vec0で10万件でも検索30ms以内。ただしINSERTは50ms/件程度。大量投入時はバッチ処理が望ましい。" |

**Even if no question was asked**, save important conversations, decisions, and work results.

## When to skip saving:
- Trivial greetings ("hi", "thanks", "ok")
- When the user explicitly asks not to save

## Quality checklist — verify BEFORE finishing your response:
- [ ] How many distinct topics? Did I call `save_memory` once per topic?
- [ ] Are my `content` fields detailed enough to be useful months later?
- [ ] Did I include file paths, commands, code, or reasoning?
- [ ] Did I save work logs and decisions, not just Q&A?
