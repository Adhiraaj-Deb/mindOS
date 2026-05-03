"""
core/ai_engine.py — Ollama interface with hybrid tool-calling support.

Strategy:
  1. PRIMARY PATH — Native Ollama tool-calling (/api/chat + tools=TOOLS).
     Works with models that support it (e.g. qwen3, llama3.1, mistral).

  2. PROMPT FALLBACK — For models that don't support native tool-calls (Gemma etc.),
     the system prompt instructs the model to output a JSON block like:
         <<<TOOL_CALL>>>
         {"tool": "save_reminder", "args": {"task": "...", ...}}
         <<<END_TOOL_CALL>>>
     Python detects and executes this, then makes a follow-up call for the reply.

  3. PLAIN TEXT  — If neither produces a tool call, the model's text is used directly.

This makes MindOS work reliably with ANY Ollama model.
"""
import json
import re
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_FALLBACK, RAG_TOP_K, MAX_HISTORY_TURNS
import core.memory_manager as memory_manager
import core.tool_executor  as tool_executor


# ── Tool schema (for models that support native Ollama tool calling) ────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_reminder",
            "description": (
                "Save a reminder for a specific date and time. "
                "ALWAYS call this when the user asks to be reminded about something."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "What to be reminded about"},
                    "date": {"type": "string", "description": "Date — e.g. 'tomorrow', 'April 20', '2025-07-14'"},
                    "time": {"type": "string", "description": "Time — e.g. '9am', '14:30', 'all day'"},
                },
                "required": ["task", "date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a task or to-do item. Call when user says they need to do something or asks to create a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title":    {"type": "string", "description": "The task description"},
                    "priority": {"type": "string", "description": "'high', 'normal', or 'low'"},
                    "due_date": {"type": "string", "description": "Optional due date"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Save a fact or personal information to long-term memory. "
                "Call when user shares info they want remembered."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to remember"},
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_idea",
            "description": "Save an idea the user wants to capture.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The idea content"},
                    "tags":    {"type": "array", "items": {"type": "string"}},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "Show all saved reminders. Call when user asks about reminders.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Show all saved tasks. Call when user asks about tasks.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_ideas",
            "description": "Show all saved ideas. Call when user asks about ideas.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ── Vault note CRUD ──────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "write_note",
            "description": (
                "Write or create a note in the Obsidian vault. "
                "Use this to save knowledge, research, facts, summaries, or any topic-specific information. "
                "Choose an appropriate existing folder or create a new one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder":  {"type": "string", "description": "Vault folder (e.g. '04_Knowledge', '06_People', '03_Projects', or a new topic name)"},
                    "title":   {"type": "string", "description": "Note title / filename (no .md needed)"},
                    "content": {"type": "string", "description": "Full markdown content of the note"},
                    "append":  {"type": "boolean", "description": "If true, append to existing note; if false (default), overwrite"},
                },
                "required": ["folder", "title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_note",
            "description": "Read the full contents of a vault note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Vault folder name"},
                    "title":  {"type": "string", "description": "Note title"},
                },
                "required": ["folder", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_note",
            "description": "Delete a note from the vault permanently.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Vault folder name"},
                    "title":  {"type": "string", "description": "Note title"},
                },
                "required": ["folder", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "List all notes in a vault folder, or list all folders if no folder given.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Folder name (empty to list all folders)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder in the vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_name": {"type": "string", "description": "Name of the folder"},
                },
                "required": ["folder_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": "Full-text search across all vault notes. Call when user asks to find something in their vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to search for"},
                },
                "required": ["query"],
            },
        },
    },
]

TOOL_MAP = {
    "save_reminder":  tool_executor.save_reminder,
    "add_task":       tool_executor.add_task,
    "save_memory":    tool_executor.save_memory,
    "add_idea":       tool_executor.add_idea,
    "list_reminders": tool_executor.list_reminders,
    "list_tasks":     tool_executor.list_tasks,
    "list_ideas":     tool_executor.list_ideas,
    # Vault note CRUD
    "write_note":     tool_executor.write_note,
    "read_note":      tool_executor.read_note,
    "delete_note":    tool_executor.delete_note,
    "list_notes":     tool_executor.list_notes,
    "create_folder":  tool_executor.create_folder,
    "search_notes":   tool_executor.search_notes,
}

# JSON schema summary injected into prompt fallback
_TOOL_PROMPT_SCHEMA = """
Available tools — use the right one for each action:

  PERSONAL DATA:
  save_reminder  → args: task (str), date (str), time (str)
  add_task       → args: title (str), priority ("high"/"normal"/"low"), due_date (str)
  save_memory    → args: fact (str)    [for quick personal facts]
  add_idea       → args: content (str), tags ([str])

  LISTS:
  list_reminders → args: (none)
  list_tasks     → args: (none)
  list_ideas     → args: (none)

  VAULT NOTES (for knowledge, research, topics, summaries):
  write_note     → args: folder (str), title (str), content (str), append (bool)
  read_note      → args: folder (str), title (str)
  delete_note    → args: folder (str), title (str)
  list_notes     → args: folder (str, optional)
  create_folder  → args: folder_name (str)
  search_notes   → args: query (str)
"""

# Regex to extract prompt-based tool calls
_TOOL_CALL_RE = re.compile(
    r"<<<TOOL_CALL>>>\s*(\{.*?\})\s*<<<END_TOOL_CALL>>>",
    re.DOTALL,
)


# ── System prompt builder ────────────────────────────────────────────────────────

def _build_system_prompt(rag_context: str, prompt_mode: bool = False) -> str:
    today = __import__('datetime').date.today().isoformat()

    vault_structure = """Vault folder structure:
  04_Knowledge/00_Meta/ — thinking meta-frameworks (start here for reasoning tasks)
  04_Knowledge/         — all knowledge notes (thinking, strategy, business, psychology)
  05_Ideas/             — productivity and learning systems
  06_People/            — notes about people
  03_Projects/          — project notes
  07_Memory/            — personal facts and memory
  08_Reminders/         — time-based reminders
  02_Tasks/             — tasks and to-dos"""

    if rag_context.strip():
        memory_block = f"""╔══════════════════════════════════════╗
║  RETRIEVED VAULT MEMORY (USE THIS)  ║
╚══════════════════════════════════════╝
{rag_context.strip()}
╔══════════════════════════════════════╗
║  END OF RETRIEVED MEMORY            ║
╚══════════════════════════════════════╝

INSTRUCTION: The memory above is retrieved from your Obsidian vault.
When answering, reference and BUILD ON the above memory.
Do NOT give a generic answer if specific memory exists above."""
    else:
        memory_block = "No relevant memory retrieved from vault for this query."

    if prompt_mode:
        return f"""You are MindOS — a personal AI second brain. Today: {today}.

You have FULL, DIRECT read/write access to the user's Obsidian vault.
You are NOT a standard chatbot. You REMEMBER because you READ and WRITE notes.

{memory_block}

{vault_structure}

{_TOOL_PROMPT_SCHEMA}

STRICT EXECUTION RULES:
1. If the above memory contains a relevant answer — USE IT. Do not ignore it.
2. To save a reminder: output <<<TOOL_CALL>>> {{"tool":"save_reminder","args":{{"task":"...","date":"...","time":"..."}}}} <<<END_TOOL_CALL>>>
3. To add a task: output <<<TOOL_CALL>>> {{"tool":"add_task","args":{{"title":"...","priority":"normal"}}}} <<<END_TOOL_CALL>>>
4. To save a fact: output <<<TOOL_CALL>>> {{"tool":"save_memory","args":{{"fact":"..."}}}} <<<END_TOOL_CALL>>>
5. To save knowledge (topic, research, explanation): output <<<TOOL_CALL>>> {{"tool":"write_note","args":{{"folder":"04_Knowledge","title":"...","content":"..."}}}} <<<END_TOOL_CALL>>>
6. To list reminders/tasks/ideas: use list_reminders / list_tasks / list_ideas
7. NEVER say you cannot access the vault. You CAN. Use write_note / read_note / list_notes.
8. Output your tool call FIRST, then your natural language response after it."""
    else:
        tool_list = "\n".join(
            f"  - {t['function']['name']}: {t['function']['description'].split('.')[0]}"
            for t in TOOLS
        )
        return f"""You are MindOS — a personal AI second brain. Today: {today}.

You have FULL, DIRECT read/write access to the user's Obsidian vault.
You REMEMBER by reading and writing notes. You are NOT a standard chatbot.

{memory_block}

{vault_structure}

Tools available:
{tool_list}

Execution rules:
- The retrieved memory above must be used when answering. Build on it; do not ignore it.
- save_reminder: whenever user says "remind me" or "remind me to"
- add_task: whenever user says "add task", "I need to", "to-do"
- save_memory: brief personal facts
- write_note: any knowledge, topic explanation, or research worth persisting
- list_notes / search_notes: when user asks what's in the vault
- NEVER say you cannot access the vault — you have full tool access."""




# ── Ollama API helpers ────────────────────────────────────────────────────────────

def _chat(model: str, messages: list, tools: list = None, timeout: int = 120) -> dict:
    """POST to /api/chat. Raises on HTTP error or timeout."""
    payload = {"model": model, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools
    r = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _execute_tool(fn_name: str, fn_args: dict) -> str:
    """Run a tool from TOOL_MAP and return the result string."""
    if isinstance(fn_args, str):
        try:
            fn_args = json.loads(fn_args)
        except json.JSONDecodeError:
            fn_args = {}
    if not isinstance(fn_args, dict):
        fn_args = {}

    if fn_name in TOOL_MAP:
        try:
            return TOOL_MAP[fn_name](**fn_args)
        except Exception as exc:
            return f"Tool error ({fn_name}): {exc}"
    return f"Unknown tool: {fn_name}"


def _extract_prompt_tool_calls(text: str) -> list:
    """
    Extract tool calls embedded by the model in prompt-engineering fallback mode.
    Returns list of (name, args) tuples.
    """
    matches = _TOOL_CALL_RE.findall(text)
    calls   = []
    for raw in matches:
        try:
            obj  = json.loads(raw)
            name = obj.get("tool", "")
            args = obj.get("args", {})
            if name and name in TOOL_MAP:
                calls.append((name, args))
        except Exception:
            pass
    return calls


def _strip_tool_blocks(text: str) -> str:
    """Remove <<<TOOL_CALL>>>...<<<END_TOOL_CALL>>> blocks from model output."""
    return _TOOL_CALL_RE.sub("", text).strip()


# ── Core ask() function ───────────────────────────────────────────────────────────

def ask(user_input: str, history: list, mode: str = "chat") -> tuple:
    """
    Send user_input + history to Ollama.
    Tries native tool-calling first; falls back to prompt-engineering mode.
    Returns (reply_text, updated_history).
    """
    try:
        if mode == "flash":
            # PURE PASSTHROUGH ROUTE: No RAG, No Tool schema, No Sync, Zero overhead
            from datetime import datetime
            import calendar
            
            now     = datetime.now()
            now_str = now.strftime('%A, %B %d, %Y')
            cal_str = calendar.TextCalendar().formatyear(now.year)
            
            sys_prompt = (
                f"You are MindOS Flash. Today is {now_str}.\n"
                f"You have perfectly accurate real-time calendar access. Here is the calendar for {now.year}:\n"
                f"{cal_str}\n"
                "If asked about dates or days of the week, simply look at the calendar above and state the exact day. "
                "Do NOT say you lack real-time information, because the exact calendar is provided to you. Do not attempt to use tools."
            )
            
            messages = [{"role": "system", "content": sys_prompt}]
            messages += history
            messages.append({"role": "user", "content": user_input})
            try:
                resp = _chat(OLLAMA_MODEL, messages) # Fast direct hit
                reply = (resp.get("message", {}).get("content") or "").strip()
                new_hist = history + [{"role": "user", "content": user_input}, {"role": "assistant", "content": reply}]
                
                cap = MAX_HISTORY_TURNS * 2
                if len(new_hist) > cap:
                    new_hist = new_hist[-cap:]
                return reply, new_hist
            except Exception as e:
                return f"Flash mode offline/error: {e}", history

        elif mode == "dashboard":
            # FAST ROUTE: Skip heavy ChromaDB sync/retrieval for the dashboard
            from core.tool_executor import list_tasks, list_reminders
            rag_context = f"CURRENT DASHBOARD STATE:\n\nTASKS:\n{list_tasks()}\n\nREMINDERS:\n{list_reminders()}"
        else:
            # 1. Update ChromaDB with any new vault files
            try:
                memory_manager.sync_vault()
            except Exception:
                pass  # Never block the user over a sync failure

            # 2. Retrieve relevant context
            try:
                rag_context = memory_manager.retrieve(user_input, top_k=RAG_TOP_K)
            except Exception:
                rag_context = ""

        final_reply = None
        used_model  = None

        # ── Execution Loop ────────────────────────────────────────────────────────
        for model_name in (OLLAMA_MODEL, OLLAMA_FALLBACK):
            
            # ATTEMPT A: Native Ollama tool-calling
            native_system = _build_system_prompt(rag_context, prompt_mode=False)
            messages_native = [{"role": "system", "content": native_system}]
            messages_native += history
            messages_native.append({"role": "user", "content": user_input})
            
            try:
                resp   = _chat(model_name, messages_native, tools=TOOLS)
                msg    = resp.get("message", {})
                t_calls = msg.get("tool_calls") or []
                if t_calls:
                    messages_native.append({
                        "role": "assistant",
                        "content": msg.get("content") or "",
                        "tool_calls": t_calls,
                    })
                    for tc in t_calls:
                        fn_name = tc.get("function", {}).get("name", "")
                        fn_args = tc.get("function", {}).get("arguments", {})
                        result  = _execute_tool(fn_name, fn_args)
                        messages_native.append({"role": "tool", "name": fn_name, "content": result})

                    followup    = _chat(model_name, messages_native)
                    final_reply = (followup.get("message", {}).get("content") or "").strip()
                    if not final_reply:
                        final_reply = "\n\n".join(m["content"] for m in messages_native if m.get("role") == "tool")
                    used_model = model_name
                    break
                else:
                    plain_text = (msg.get("content") or "").strip()
                    if plain_text:
                        final_reply = plain_text
                        used_model  = model_name
                        break
            except Exception as e:
                print(f"ATTEMPT A ERROR ({model_name}):", e)
                # Fall through to Attempt B for the SAME model
                pass

            # ATTEMPT B: Prompt-engineering tool calling
            prompt_system   = _build_system_prompt(rag_context, prompt_mode=True)
            messages_prompt = [{"role": "system", "content": prompt_system}]
            messages_prompt += history
            messages_prompt.append({"role": "user", "content": user_input})
            
            try:
                resp        = _chat(model_name, messages_prompt)
                raw_content = (resp.get("message", {}).get("content") or "").strip()
                used_model  = model_name

                p_calls = _extract_prompt_tool_calls(raw_content)
                if p_calls:
                    tool_results = []
                    for fn_name, fn_args in p_calls:
                        result = _execute_tool(fn_name, fn_args)
                        tool_results.append(result)

                    cleaned = _strip_tool_blocks(raw_content)
                    if cleaned:
                        final_reply = "\n\n".join(tool_results) + "\n\n" + cleaned
                    else:
                        final_reply = "\n\n".join(tool_results)
                else:
                    final_reply = raw_content
                
                # Only break loop if the model actually generated a valid text response
                if final_reply.strip():
                    break
                else:
                    print(f"Model {model_name} generated empty response, trying next model...")
                    continue
            except Exception as e:
                print(f"ATTEMPT B ERROR ({model_name}):", e)
                continue # Now that both A and B failed natively on this model, fall to fallback model.

        # ── Last resort ───────────────────────────────────────────────────────
        if not final_reply:
            final_reply = (
                "I'm sorry, I couldn't process that request. "
                "Please make sure Ollama is running and try again."
            )

        # 3. Update history (system prompt is never stored in history)
        new_history = history + [
            {"role": "user",      "content": user_input},
            {"role": "assistant", "content": final_reply},
        ]
        cap = MAX_HISTORY_TURNS * 2
        if len(new_history) > cap:
            new_history = new_history[-cap:]

        return final_reply, new_history

    except requests.ConnectionError:
        return (
            "Cannot connect to Ollama.\n"
            "Please make sure the Ollama app is running and try again.",
            history,
        )
    except requests.Timeout:
        return "Ollama is taking too long to respond. Please try a shorter question.", history
    except Exception as exc:
        return f"Error: {exc}", history


# ── Utility ───────────────────────────────────────────────────────────────────────

def ollama_status() -> bool:
    """Return True if Ollama is reachable."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}", timeout=3)
        return r.status_code == 200
    except Exception:
        return False
