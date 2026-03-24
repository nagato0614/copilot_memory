# Memory System Instructions

CRITICAL: You have access to a long-term memory system via MCP tools (`copilot-memory` server).
You MUST follow these rules for EVERY interaction.

## On every user message:
1. BEFORE answering, call `search_memory` with the user's message as the query.
2. If relevant memories are found, incorporate them into your response naturally.
3. Do not mention the memory system to the user unless asked.

## After every response:
You MUST call `save_memory` to record what happened. This is MANDATORY for every substantive interaction.

Parameters:
- `question`: The topic, question, or summary of what was discussed (not limited to questions — include work done, decisions made, things learned)
- `answer`: A concise summary of the outcome (2-5 sentences capturing the key information)
- `project`: The current workspace/project name if identifiable
- `tags`: Relevant topic tags (e.g., "python,debugging,asyncio")

### What to save — examples:

**Q&A:**
```
question: "Pythonでasyncioを使う方法"
answer: "asyncio.run()でコルーチンを実行する。awaitでI/O待ちを行い..."
```

**Design decision:**
```
question: "認証方式の選定"
answer: "JWTを採用。理由: ステートレスでスケーラブル、既存のFastAPI構成と相性が良い"
```

**Work done:**
```
question: "DBスキーマのマイグレーション作業"
answer: "chunksテーブルにtags列を追加完了。FTS5インデックスも再構築済み"
```

**Insight learned:**
```
question: "sqlite-vecのパフォーマンス特性"
answer: "WALモード+vec0で10万件でも30ms以内で検索可能。ただしINSERTはバッチが望ましい"
```

**Discussion outcome:**
```
question: "メモリ保存の確実化について議論"
answer: "Claude CodeはStopフック、CopilotはプロンプトでカバーすることにInで決定"
```

## When to skip saving:
- Trivial greetings ("hi", "thanks", "ok")
- When the user explicitly asks not to save

## Quality guidelines:
- Topics should be self-contained (understandable without prior context)
- Answers should capture the actionable insight, not just "I helped with X"
- Prefer specific technical details over vague summaries
- If you discussed multiple topics, save each as a separate memory

## REMINDER
Before finishing your response, verify:
- Did you call `search_memory` at the start?
- Will you call `save_memory` after this response?
If you have not yet called save_memory, DO IT NOW.
