# Nexidion Internal Linking System

A core component of any knowledge base is the ability to connect your thoughts. Nexidion features a highly robust, "self-healing" internal linking engine designed to ensure your links never break, even as your vault evolves.

## The Problem: Fragile Links
In many note-taking apps, linking to a page using `[[Note Title]]` is fragile. If you rename the note "Note Title" to "Completed Project", every link pointing to it across your entire vault breaks until you manually update them.

## The Solution: Robust UUID Links
Nexidion solves this by using a "Strong Link" architecture under the hood. Instead of relying on the note's title, Nexidion binds links to the node's permanent, hidden ID (UUID). 

If you link to a node called "Project A" and later rename it to "Completed Project", **the link automatically updates and remains perfectly intact** because the system is tracking the node's internal ID, not its name.

---

## Link Syntax

Nexidion supports three types of links inside the Markdown editor:

### 1. Strong Links (Recommended)
**Syntax:** `[[Display Text|Node-UUID]]`
*   **How it works:** This is the standard Nexidion link format. The `Display Text` is what you see when reading the note. The `Node-UUID` is what the system uses to find the destination.
*   **Example:** `[[My thoughts on architecture|a1b2c3d4-e5f6-4a3b-8c2d-1e9f0a2b1c3d]]`
*   **Note:** *You do not need to memorize UUIDs!* The editor handles creating these for you automatically via Autocomplete (see below).

### 2. Weak Links (Legacy & Quick Entry)
**Syntax:** `[[Exact Node Title]]` or `[[Exact Node Title|Custom Display Text]]`
*   **How it works:** This is a purely title-based link. When you click it, Nexidion dynamically searches your vault for a node with that exact title. 
*   **Use case:** Useful for quickly typing out ideas, or for backwards compatibility with imported markdown files. 
*   **Warning:** If you have multiple nodes with the exact same title, clicking a weak link will prompt the system to ask you which one you meant, offering to permanently fix the link for you.

### 3. Standard External Links
**Syntax:** `[Website Name](https://example.com)`
*   **How it works:** Standard Markdown links are used strictly for external web addresses.

---

## How to Create Internal Links (Autocomplete)

You do not need to manually copy and paste UUIDs to create strong, unbreakable links. Nexidion's intelligent editor does the heavy lifting for you.

1.  In the editor, simply type `[[` followed by the name of the note you want to link to.
2.  An **Autocomplete Dropdown** will appear, searching your vault for matching nodes.
3.  Use your arrow keys to select the correct node and press `Enter` (or click it).
4.  The editor will instantly convert your search into a permanent Strong Link: `[[Node Name|uuid-string]]`.

---

## For Developers: Under the Hood

For those interested in the technical architecture, Nexidion's custom Markdown pipeline solves a notorious React limitation known as the "Hydration Trap."

Creating semantic Abstract Syntax Tree (AST) nodes for internal links often causes React to crash if block elements (like `<div>`) are rendered inside markdown paragraphs (`<p>`). 

To bypass this, Nexidion uses a custom Remark plugin (`@nexidion/remark-internal-links`) that acts as the single source of truth. It intercepts the `[[...]]` syntax during parsing and instantly transforms it into a standard HTML `<span>` tag packed with `data-*` attributes. 

*Example:* 
`[[API v3]]` is parsed securely into:
`<span class="internal-link" data-target="API v3" data-display-text="API v3">API v3</span>`

By using `rehype-raw` in the frontend, React safely renders this as an inline element, completely eliminating hydration crashes while preserving interactive, single-page-application routing.