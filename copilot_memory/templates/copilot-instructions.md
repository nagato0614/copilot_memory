# Memory System Instructions

CRITICAL: You have access to a long-term memory system via MCP tools (`copilot-memory` server).
You MUST follow these rules for EVERY interaction.

## On every user message:
1. BEFORE answering, call `search_memory` with the user's message as the query.
2. If relevant memories are found, incorporate them into your response naturally.
3. Do not mention the memory system to the user unless asked.

## After every response:
You MUST call `save_memory` **multiple times** — one call per distinct topic, fact, or action.
Do NOT bundle everything into a single save. Split into focused, granular memories.

Parameters:
- `question`: A specific topic title (short, searchable, self-contained)
- `answer`: Detailed explanation with concrete specifics (3-8 sentences). Include: file paths, commands, code snippets, version numbers, error messages, reasoning, trade-offs — anything that would help someone understand later.
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
question: "認証機能の追加で変更したファイル一覧"
answer: "新規作成: app/auth/jwt.py (トークン生成), app/auth/deps.py (get_current_user依存), app/models/user.py (Userモデル), app/routers/auth.py (login/registerエンドポイント)。変更: app/main.py (ルーター追加), requirements.txt (python-jose[cryptography], passlib[bcrypt]追加)。"
tags: "fastapi,auth,file-changes"
```

**Save 4 — Learned insight:**
```
question: "FastAPIのDepends()でJWT認証を注入するパターン"
answer: "get_current_user = Depends(oauth2_scheme) → トークンデコード → DBからユーザー取得、という3段階。oauth2_schemeはOAuth2PasswordBearerでtokenUrl='auth/login'を指定。エンドポイントの引数にcurrent_user: User = Depends(get_current_user)を追加するだけで認証が有効になる。"
tags: "fastapi,auth,depends,pattern"
```

## When to skip saving:
- Trivial greetings ("hi", "thanks", "ok")
- When the user explicitly asks not to save

## Quality guidelines:
- **1 topic = 1 save_memory call** — never bundle multiple topics
- `question` is short and searchable (a title, not a full sentence)
- `answer` is detailed: include file paths, commands, code, numbers, reasoning
- Each memory must be understandable on its own without prior context
- Always include `tags` for better search
- Prefer 3-5 saves per substantial interaction over 1 vague save

## REMINDER
Before finishing your response, verify:
- Did you call `search_memory` at the start?
- How many distinct topics did this interaction cover? Call `save_memory` once per topic.
- Are your answers detailed enough to be useful months later?
