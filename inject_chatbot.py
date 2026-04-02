import os
from pathlib import Path

project_root = Path("c:/Users/karth/OneDrive/Pictures/copy/project")

# CSS and JS to inject
inject_css = '<link rel="stylesheet" href="{rel_path}ai_assistant/roadmind.css">\n'
inject_js = '<script src="{rel_path}ai_assistant/roadmind.js" defer></script>\n'

html_files = list(project_root.rglob("*.html"))
modified_count = 0

for html_file in html_files:
    # Calculate depth relative to project root
    try:
        rel_path_to_file = html_file.relative_to(project_root)
    except ValueError:
        continue # File not strictly inside root

    depth = len(rel_path_to_file.parents) - 1 # -1 because parents includes the root itself
    
    if depth == 0:
        prefix = ""
    else:
        prefix = "../" * depth

    css_tag = inject_css.format(rel_path=prefix)
    js_tag = inject_js.format(rel_path=prefix)

    with open(html_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Avoid injecting multiple times
    if "roadmind.js" in content or "roadmind.css" in content:
        continue

    # Insert before closing </head>
    if "</head>" in content.lower():
        # case-insensitive replace by finding index
        orig_content = content.lower()
        idx = orig_content.find("</head>")
        new_content = content[:idx] + "    " + css_tag + "    " + js_tag + content[idx:]
        
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        modified_count += 1
    elif "<body>" in content.lower():
        # Fallback if no head, inject before body
        orig_content = content.lower()
        idx = orig_content.find("<body>")
        new_content = content[:idx] + "    " + css_tag + "    " + js_tag + content[idx:]
        
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        modified_count += 1
    else:
        # Just prepend it if both fail
        new_content = css_tag + js_tag + content
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        modified_count += 1

print(f"Successfully injected chatbot into {modified_count} HTML files out of {len(html_files)}")
