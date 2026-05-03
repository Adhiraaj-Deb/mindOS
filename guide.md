# MindOS: Your Local AI Second Brain

Welcome to **MindOS**, a completely localized, intelligent second brain that lives directly inside your Obsidian vault. MindOS connects the notes you take with a powerful local AI model (Ollama + Gemma), allowing you to not only store your thoughts but also converse with them without ever relying on the internet.

## What is MindOS?

MindOS acts as a dynamic bridge between your personal data and a Local Large Language Model (LLM). 

Traditionally, a second brain (like Obsidian) only serves as a static notebook. To find things, you have to search for them manually. MindOS completely changes this paradigm by turning your vault into a "thinking" entity. 

**Core capabilities:**
* **Retrieval-Augmented Generation (RAG):** MindOS reads all your `.md` files, converts the text into mathematical embeddings, and stores them via ChromaDB. Whenever you ask a question, MindOS searches for the most relevant memories in milliseconds and feeds them to the AI to answer contextually.
* **Continuous Learning Engine:** MindOS is always learning. It watches your vault for modifications—whenever a file changes, it silently re-indexes the new content, ensuring your AI's knowledge base is never outdated.
* **Privacy-First:** The engine runs exclusively on your local hardware using Python, ChromaDB, and Ollama. None of your private thoughts, tasks, or ideas ever touch the cloud.

---

## How to Start MindOS

To start chatting with your second brain, open your terminal (Command Prompt or PowerShell) inside the `MindOS` directory and execute:

```powershell
python mindos_brain.py
```
*Note: MindOS is packaged with a smart bootstrapper. Because it utilizes a localized virtual environment (`.venv`) to manage large AI packages, running standard `python` will automatically detect the environment and reboot inside the correct isolated shell automatically!*

---

## Conversing & Extracting

Once booted, you will see a command prompt: `Enter your question (or 'exit' to quit):`.

MindOS detects two styles of input: **Action Commands (Saving)** and **Questions (Retrieval)**.

### 1. Action Commands (Saving Data)
MindOS features real-time parsing commands. If you tell it to save something, it skips answering, instantly injects it into your vault, and embeds it right away.

* **Save a Memory:** Start your sentence with `Remember that`, `Save this`, or `Note this`. 
  > *Example: "Remember that I want to build an AI startup next year."*
  > *Result:* Saves to `07_Memory/memory.md` with today's timestamp.
  
* **Save an Idea:** Include the word `idea` in your sentence.
  > *Example: "I have an idea: creating a fitness tracking app using python."*
  > *Result:* Saves neatly to `05_Ideas/ideas.md`.
  
* **Create a Task:** Include the word `task` or `todo`.
  > *Example: "Add a task: finish reading the new AI research paper."*
  > *Result:* Formats and saves as an actionable checkbox `- [ ]` into `02_Tasks/tasks.md`.

### 2. Questions (Retrieval)
If your input is naturally phrased as a question (ends with a `?` or starts with Who/What/Where/When/Why/How), MindOS will search your brain.

> *Example: "What are the ideas I've written down recently?"*
> *Result:* MindOS will search `05_Ideas`, bring those notes to the AI, and the AI will summarize and present them to you conversationally.

> *Example: "What is my main goal?"*
> *Result:* MindOS will search `07_Memory`, locate the memory you saved ("I want to build an AI startup"), and articulate a cohesive answer referencing that memory.

---

## The Vault Structure

MindOS expects standard Markdown files and is currently organized around the following foundational structure:

* `00_Dashboard` - High-level views and overviews.
* `01_Daily` - Daily check-ins or journal entries.
* `02_Tasks` - Actionable items. (`task:` command target)
* `03_Projects` - Ongoing active projects.
* `04_Knowledge` - Evergreen notes or tutorials.
* `05_Ideas` - Raw brain dumps. (`idea` command target)
* `06_People` - CRM / relationship contexts.
* `07_Memory` - Saved instant facts. (`remember` command target)

*You can add as many directories and Markdown files as you want. MindOS will natively discover `.md` files dynamically, wherever they are kept inside the folder.*

Enjoy building your second brain!
