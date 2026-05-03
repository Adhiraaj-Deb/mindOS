# MindOS: The Local AI Second Brain

MindOS is a sophisticated, privacy-first personal intelligence layer built on top of an Obsidian vault. It transforms static notes into a living, breathing digital consciousness that you can converse with, query, and command—all powered by local hardware.

---

## 🚀 The Simple Explanation (High-Level)

### What is MindOS?
Imagine if your notes could talk back to you. MindOS is an application that sits on top of your **Obsidian** vault and connects it to a powerful **Local AI**. Instead of searching through folders to find information, you just ask MindOS a question. It reads through your notes, finds the relevant information, and answers you conversationally.

### What can it do?
*   **Talk to your Notes:** Ask things like "What was that idea I had about a fitness app?" or "What are my goals for this year?" and get an instant summary based on your actual writing.
*   **Quick Capture:** Simply type "Remember that I need to buy milk" or "I have an idea for a new book," and MindOS will automatically file it into the correct note in your Obsidian vault.
*   **Task Management:** Tell it to "Add a task to finish the report," and it will create a checkbox in your `tasks.md` file.
*   **100% Private:** Nothing ever leaves your computer. No cloud, no subscription, no data tracking. It’s your brain, on your hardware.

---

## 🛠️ The Technical Explanation (Deep Dive)

### Architecture & System Design
MindOS is built as a **Retrieval-Augmented Generation (RAG)** pipeline designed for low-latency personal knowledge management. It operates as a bridge between a localized **Vector Database** and a **Large Language Model (LLM)**.

#### 1. The Core Tech Stack
*   **Language:** Python 3.10+
*   **Frontend/UI:** PyQt6 (Desktop Application)
*   **LLM Engine:** [Ollama](https://ollama.ai/) (Running `gemma:2b` as primary and `gemma:7b` as fallback).
*   **Vector Store:** [ChromaDB](https://www.trychroma.com/) for persistent semantic indexing.
*   **Intelligence Layer:** Custom NLP parsing for action extraction (Tasks/Ideas/Memories).
*   **Storage Interface:** Direct filesystem manipulation of `.md` files within an Obsidian vault.

#### 2. How It Works (The Lifecycle)
1.  **Semantic Indexing:** Upon startup and during runtime, a background worker monitors the Obsidian vault. New or modified Markdown files are parsed, chunked, and converted into mathematical embeddings (vectors) which are stored in ChromaDB.
2.  **The RAG Pipeline:** When a user asks a question, MindOS converts the query into a vector and performs a similarity search against ChromaDB. The top `N` most relevant text chunks are retrieved and injected into the AI's "context window" as ground-truth data.
3.  **Command Extraction:** MindOS uses pattern matching and LLM-assisted intent recognition to distinguish between a *Question* (which triggers a search) and an *Action* (which triggers a write operation).
    *   **Write Operations:** Use direct file I/O to append formatted Markdown to specific "Anchor Files" (e.g., `tasks.md`, `ideas.md`).
4.  **Local Execution:** By utilizing `Ollama` as the inference server, MindOS ensures that LLM weights are loaded and executed entirely on the local CPU/GPU, eliminating the need for external API calls.

#### 3. Folder Infrastructure
MindOS organizes your digital life into a structured hierarchy:
*   `00-09` Indexed Directories: Categorized storage for Daily notes, Tasks, Knowledge, etc.
*   `chroma_db/`: The persistent local brain containing all semantic embeddings.
*   `.venv/`: An isolated Python environment containing all necessary AI dependencies (Transformers, PySide6, etc.).

---

## 🛠 Installation & Usage
1.  Ensure [Ollama](https://ollama.com/) is installed and running.
2.  Pull the required models: `ollama pull gemma:2b`.
3.  Launch the application:
    ```powershell
    python mindos_app.py
    ```
4.  Interact via the PyQt6 dashboard to chat with your vault in real-time.


---

## 📄 License & Attribution

MindOS is open-source software licensed under the **MIT License**.

### Give Credit Where It's Due
While you are free to use, modify, and distribute this software, it would be greatly appreciated if you gave a mention or link back to the original repository. 

If you use MindOS in a project or build something on top of it, please attribute it to:
**Adhiraaj Deb** ([@Adhiraaj-Deb](https://github.com/Adhiraaj-Deb))

---

*Built for privacy. Powered by local intelligence.*
