import json

DEMO_INSTRUCTION = "Create a second Test Node UNDER Test 1, and update the content of Test 1"

DEMO_FINISH_SUMMARY = "Completed both tasks:\n1. Created a new \"Test Node\" (UUID: c4a347e5-facd-4224-97b4-7c811f6e23c2) as a child under \"Test 1\"\n2. Updated the content of \"Test 1\" to include a reference to the new child node with an internal link, and updated its AI summary to reflect the new structure"

DEMO_OPERATIONS = json.loads(r"""
[
    {
        "detail": {
            "ai_summary": "- This is a child test node created under Test 1\n- It demonstrates the hierarchical structure of the Nexidion vault\n- Content can be replaced with actual information as needed",
            "content": "# Test Node\n\nThis is a test node created under Test 1. It serves as a child node to demonstrate the hierarchical structure of the Nexidion vault.\n\n## Purpose\n\nThis node can be used for:\n- Testing node creation and hierarchy\n- Organizing related information under Test 1\n- Demonstrating parent-child relationships in the knowledge base\n\nFeel free to replace this content with actual information as needed.",
            "parent_id": "f9e941b2-b9bf-45a9-8657-77c519c0bce6",
            "title": "Test Node"
        },
        "node_id": "c4a347e5-facd-4224-97b4-7c811f6e23c2",
        "operation": "create_node",
        "timestamp": "2026-05-21T09:53:58.928320+00:00"
    },
    {
        "detail": {
            "ai_summary": "- This node contains placeholder content with a child test node\n- A new Test Node has been created as a child to demonstrate hierarchy\n- Content includes lorem ipsum filler and can be updated as needed",
            "content": "# Test 1\n\nThis is the first paragraph of dummy content for Test 1. It serves as a placeholder to demonstrate how content is structured within a Nexidion vault node. You can replace this text with any information you find useful, such as notes, references, or personal thoughts.\n\n## Child Nodes\n\nThis node now contains a child node: [[Test Node|c4a347e5-facd-4224-97b4-7c811f6e23c2]], which demonstrates the hierarchical organization available in the vault.\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.\n\nExcepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. Curabitur pretium tincidunt lacus. Nulla gravida orci a odio. Nullam varius, turpis et commodo pharetra, est eros bibendum elit, nec luctus magna felis sollicitudin mauris."
        },
        "node_id": "f9e941b2-b9bf-45a9-8657-77c519c0bce6",
        "operation": "write_node",
        "timestamp": "2026-05-21T09:54:08.525233+00:00"
    }
]
""")
