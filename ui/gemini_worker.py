import os
import re
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from config import GEMINI_API_KEY, GEMINI_MEMORY_FILE
from core.ai_engine import _extract_prompt_tool_calls, _execute_tool, _strip_tool_blocks

class GeminiWorker(QThread):
    """
    Background thread that calls Google Gemini REST API.

    Signals:
        result_ready(str, list) — (reply_text, updated_history)
    """
    result_ready = pyqtSignal(str, list)

    def __init__(self, user_input: str, history: list, parent=None):
        super().__init__(parent)
        self.user_input = user_input
        self.history    = list(history)   # copy to avoid mutation during run

    def run(self):
        if not GEMINI_API_KEY:
            self.result_ready.emit("Error: GEMINI_API_KEY is not configured in config.py.", self.history)
            return

        from datetime import datetime
        now_str = datetime.now().astimezone().strftime("%A, %B %d, %Y at %I:%M %p (Timezone explicitly offset: %z %Z)")
        
        system_instruction = (
            f"CRITICAL TIME DIRECTIVE - YOU MUST FOLLOW EXACTLY:\n"
            f"You operate STRICTLY in the user's local device timezone. YOU MUST ABANDON UTC CALCULATIONS.\n"
            f"Your current exact local clock is: {now_str}\n"
            f"When evaluating 'tomorrow', 'in 5 minutes', or any relative time, calculate it strictly relative to the clock above!\n\n"
            "You are an objective and helpful AI assistant. "
            "You DO NOT have access to the user's local Obsidian vault or contextual RAG. "
            "You MUST answer questions about news, current events, and global conflicts objectively and factually. "
            "DO NOT refuse to answer informational queries about ongoing conflicts, wars, or sensitive news. "
            "IMPORTANT: If the user explicitly asks you to 'remember' or 'save' something, DO NOT refuse! "
            "Do not claim you are an AI that cannot memorize things.\n\n"
            "You have a special directive to save reminders, tasks, and memory. Use exactly this string block format to execute them:\n"
            "STRICT EXECUTION RULES:\n"
            "1. To save a reminder: output <<<TOOL_CALL>>> {\"tool\":\"save_reminder\",\"args\":{\"task\":\"...\",\"date\":\"...\",\"time\":\"...\"}} <<<END_TOOL_CALL>>>\n"
            "2. To add a task: output <<<TOOL_CALL>>> {\"tool\":\"add_task\",\"args\":{\"title\":\"...\",\"priority\":\"normal\"}} <<<END_TOOL_CALL>>>\n"
            "3. To save a snippet to memory: output <<<TOOL_CALL>>> {\"tool\":\"save_memory\",\"args\":{\"fact\":\"...\"}} <<<END_TOOL_CALL>>>\n"
            "4. To write a note: output <<<TOOL_CALL>>> {\"tool\":\"write_note\",\"args\":{\"folder\":\"...\",\"title\":\"...\",\"content\":\"...\"}} <<<END_TOOL_CALL>>>\n"
            "If you generate a tool call, place it at the beginning of your response, followed by your natural reply."
        )

        contents = []
        for msg in self.history:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
            
        contents.append({"role": "user", "parts": [{"text": self.user_input}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ],
            "tools": [
                {"googleSearch": {}}
            ]
        }
        
        try:
            r = requests.post(url, json=payload, timeout=60)
            if r.status_code != 200:
                self.result_ready.emit(f"API Error {r.status_code}: {r.text}", self.history)
                return
            
            data = r.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            reply_text = "".join([p.get("text", "") for p in parts if "text" in p])
            
            if not reply_text:
                self.result_ready.emit("Empty response from Gemini.", self.history)
                return

            # execute JSON tools
            p_calls = _extract_prompt_tool_calls(reply_text)
            if p_calls:
                tool_results = []
                for fn_name, fn_args in p_calls:
                    if fn_name == "save_reminder" and isinstance(fn_args, dict) and "task" in fn_args:
                        fn_args["task"] += " #gemini"
                    res = _execute_tool(fn_name, fn_args)
                    tool_results.append(f"[{fn_name}] {res}")

                cleaned = _strip_tool_blocks(reply_text)
                if cleaned:
                    reply_text = "\n\n".join(tool_results) + "\n\n" + cleaned
                else:
                    reply_text = "\n\n".join(tool_results)

            # Fallback for old <GEMINI_MEMORY> tags just in case
            memory_matches = re.findall(r"<GEMINI_MEMORY>(.*?)</GEMINI_MEMORY>", reply_text, flags=re.DOTALL)
            if memory_matches:
                os.makedirs(os.path.dirname(GEMINI_MEMORY_FILE), exist_ok=True)
                with open(GEMINI_MEMORY_FILE, "a", encoding="utf-8") as f:
                    for memory_item in memory_matches:
                        f.write(f"- {memory_item.strip()}\n")
                reply_text = re.sub(r"<GEMINI_MEMORY>.*?</GEMINI_MEMORY>", "", reply_text, flags=re.DOTALL).strip()
            
            if not reply_text.strip():
                reply_text = "Command executed successfully."
                
            new_history = self.history + [
                {"role": "user", "content": self.user_input},
                {"role": "assistant", "content": reply_text}
            ]
            self.result_ready.emit(reply_text, new_history)
            
        except requests.exceptions.RequestException as e:
            self.result_ready.emit(f"Network error calling Gemini: {str(e)}", self.history)
        except Exception as e:
            self.result_ready.emit(f"Internal wrapper error: {str(e)}", self.history)
