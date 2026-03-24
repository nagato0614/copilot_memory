# Memory System Instructions

MANDATORY: You have access to a long-term memory system via MCP tools (`copilot-memory` server).
You MUST follow these rules for EVERY interaction without exception.

## BEFORE every response:
1. Call `search_memory` with the user's message as the query. DO NOT SKIP THIS STEP.
2. If relevant memories are found, incorporate them into your response naturally.
3. Do not mention the memory system to the user unless asked.

## AFTER every response:
You MUST call `save_memory` **multiple times** — one call per distinct topic, fact, or action.
Do NOT bundle everything into a single save. Split into focused, granular memories.

## What to save — it's not just Q&A:

Save ALL of the following categories. `question` field = topic/title (not necessarily a question):

| Category | `question` example | `answer` example |
|---|---|---|
| Q&A | "Pythonでasyncioの使い方" | "asyncio.run()でコルーチンを実行。awaitでI/O待ちを非同期化..." |
| Design decision | "認証方式の選定理由" | "JWTを採用。理由: ステートレス、FastAPIのDependsと相性良..." |
| Work log | "DBマイグレーション作業完了" | "chunksテーブルにtags列追加。ALTER TABLE chunks ADD COLUMN tags TEXT..." |
| Insight | "sqlite-vecのパフォーマンス特性" | "WALモード+vec0で10万件30ms以内。ただしINSERTは50ms/件..." |
| Discussion | "メモリ保存戦略の合意" | "Claude Codeはhookで自動保存、Copilotはプロンプトでカバーに決定..." |

**Even if no question was asked**, save important conversations, decisions, and work results.

## Parameters:
- `question`: A specific topic title (short, searchable, self-contained — NOT a full sentence)
- `answer`: Detailed explanation (3-8 sentences). Include: file paths, commands, code snippets, version numbers, error messages, reasoning, trade-offs
- `project`: The current workspace/project name
- `tags`: Relevant topic tags (e.g., "python,fastapi,auth")

## How to split into multiple saves:

One conversation often covers multiple topics. Save each separately.

Example: User asks "FastAPIで認証を実装して" and you implement JWT auth.

**Save 1 — Design decision:**
```
question: "FastAPI認証方式の選定"
answer: "JWTベースの認証を採用。python-joseライブラリを使用。理由: (1) ステートレスでスケーラブル (2) FastAPIのDependsパターンと相性が良い (3) フロントエンドがSPAなのでcookieよりAuthorizationヘッダーが適切。セッション方式はRedis依存が増えるため不採用。"
tags: "fastapi,auth,jwt,design-decision"
```

**Save 2 — Implementation detail:**
```
question: "FastAPI JWTトークン生成の実装"
answer: "app/auth/jwt.py にcreate_access_token()を実装。SECRET_KEYは環境変数JWT_SECRETから取得。アルゴリズムはHS256、有効期限はACCESS_TOKEN_EXPIRE_MINUTES=30。jose.jwt.encode()でペイロード{sub: user_id, exp: datetime}をエンコード。リフレッシュトークンは未実装。"
tags: "fastapi,jwt,python,implementation"
```

**Save 3 — File changes:**
```
question: "認証機能で変更したファイル一覧"
answer: "新規: app/auth/jwt.py, app/auth/deps.py, app/models/user.py, app/routers/auth.py。変更: app/main.py (ルーター追加), requirements.txt (python-jose, passlib追加)。"
tags: "fastapi,auth,file-changes"
```

**Save 4 — Pattern/insight:**
```
question: "FastAPIのDepends()でJWT認証を注入するパターン"
answer: "get_current_user = Depends(oauth2_scheme) → トークンデコード → DBからユーザー取得、の3段階。oauth2_schemeはOAuth2PasswordBearerでtokenUrl='auth/login'。エンドポイント引数にcurrent_user: User = Depends(get_current_user)を追加するだけで認証有効。"
tags: "fastapi,auth,depends,pattern"
```

## When to skip saving:
- Trivial greetings ("hi", "thanks", "ok")
- When the user explicitly asks not to save

## Quality checklist — verify BEFORE finishing your response:
- [ ] Did I call `search_memory` at the start?
- [ ] How many distinct topics did this interaction cover? Did I call `save_memory` once per topic?
- [ ] Are my `answer` fields detailed enough to be useful months later?
- [ ] Did I include file paths, commands, code, or reasoning where applicable?
- [ ] Did I save work logs and decisions, not just Q&A?
