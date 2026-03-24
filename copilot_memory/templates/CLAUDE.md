# Memory System Instructions

You have access to a long-term memory system via MCP tools (`copilot-memory` server). Follow these rules for EVERY interaction:

## On every user message:
1. BEFORE answering, call `search_memory` with the user's question as the query.
2. If relevant memories are found, incorporate them into your response naturally.
3. Do not mention the memory system to the user unless asked.

## After every response:
1. Call `save_memory` with:
   - `question`: The user's question (condensed if very long)
   - `answer`: A concise summary of your response (2-5 sentences capturing the key information)
   - `project`: The current workspace/project name if identifiable
   - `tags`: Relevant topic tags (e.g., "python,debugging,asyncio")

## When to skip saving:
- Trivial greetings or meta-questions about the memory system itself
- When the user explicitly asks not to save

## Quality guidelines for saved memories:
- Questions should be self-contained (understandable without prior context)
- Answers should capture the actionable insight, not just "I helped with X"
- Prefer specific technical details over vague summaries
