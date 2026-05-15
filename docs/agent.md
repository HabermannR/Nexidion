Here is the markdown documentation for the AI Agent feature. You can save this file as `agent.md` in your `docs/` folder (or your preferred documentation location).

---

# Using the Nexidion AI Agent (Task Runner)

Nexidion includes an optional, autonomous background worker (the AI Task Runner) that can act as your personal knowledge assistant. Instead of just answering questions, this agent has "hands" — it can reorganize your notes, summarize subtrees, create new documents, or execute bulk changes based entirely on your natural language instructions.

## 1. Granting the Agent Access to Your Vault

The system automatically creates a special system user named **LLM Assistant** when you deploy Nexidion. However, for strict security, this assistant has zero access to your data by default. 

Before you can issue tasks, you must invite the agent into your vault:

1. Go to the **Admin** dashboard (top right menu).
2. Scroll down to **Vault Access Management**.
3. Select your Vault on the left.
4. Under "Current access", select `LLM Assistant (default-llm) [LLM]` from the dropdown and click **Add**.

![Granting Agent Access](images/agent_access.jpg)

## 2. Issuing a Task to the Agent

Once the agent has access, navigate back to your workspace. Open the **Agent** tab on the right-hand panel.

### Step 1: Select Context (Optional but Recommended)
You can give the agent specific nodes to focus on by selecting them in the navigation tree on the left (hover over a node's icon and click the checkbox). The selected nodes will appear under "Context nodes" in the Agent panel.

### Step 2: Write Your Instruction
Write what you want the agent to do using plain natural language. You can ask it to:
*   *"Write an introduction to Obsidian."*
*   *"Summarize all the child nodes and put the summary in the parent node."*
*   *"Reorganize these selected nodes into folders based on topic."*
*   *"Read my meeting notes and extract a list of action items into a new node."*

### Step 3: Queue Task
Click **Queue Task**. 

![Queueing a Task](images/agent2.jpg)

## 3. Reviewing the Agent's Work

By default, the background Task Runner checks for new tasks every 5 seconds. Once it picks up your task, it will work autonomously in the background.

When finished, the task will show as **COMPLETED** in the task history list. 

**Detailed Logs & Clickable Links:**
Click on a completed task to expand its details. The agent will present a written summary of exactly what it did and list the specific internal tools it used (e.g., `Wrote node`, `Moved node`). 

All UUIDs listed in the operations log are **clickable links**. You can click right on the ID to instantly jump to the node the agent just created or modified!

![Task Details and Logs](images/agent3.jpg)

## 4. Track Changes & AI Summaries

**Full Version Control:**
You never have to worry about the AI ruining your notes. Whenever the agent modifies a node, it creates a new version. In the **Versions** tab, you will clearly see edits attributed to the "LLM Assistant". If you don't like what the agent wrote, you can easily revert back to your previous human-written version.

![LLM Version History](images/llm_version.jpg)

**AI Summaries:**
The agent can also attach dedicated summary blocks to the top of nodes, giving you a quick TL;DR of large documents before you dive into reading them.

![AI Summary Block](images/agent_summary.jpg)

## 5. Protecting Sensitive Nodes (The Lock Icon)

If you have specific nodes that contain highly sensitive data that you absolutely do not want the AI to read or modify (like passwords, personal journal entries, or API keys), you can lock them.

Click the node's icon to open the type selector, and change it to the **Locked / Private** icon. 
*While most node icons in Nexidion are purely cosmetic, the Lock icon is functional.* It explicitly forbids the AI agent from accessing or editing the contents of that node.

![Locking a Node](images/lock.jpg)