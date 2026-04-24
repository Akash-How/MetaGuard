import re
import sys

def check_jsx(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    stack = []
    
    # Very basic html tag matcher for JSX
    tag_pattern = re.compile(r'<\s*(/?)\s*([a-zA-Z0-9_-]+)([^>]*?)>')
    
    self_closing = ['br', 'img', 'input', 'hr', 'path', 'polygon', 'line', 'polyline', 'circle', 'rect']
    
    for i, line in enumerate(lines):
        line_clean = re.sub(r'//.*', '', line)
        line_clean = re.sub(r'{/\*.*?\*/}', '', line_clean)
        
        for match in tag_pattern.finditer(line_clean):
            is_closing = match.group(1) == '/'
            tag_name = match.group(2)
            attrs = match.group(3)
            
            if not is_closing and attrs.strip().endswith('/'):
                continue
                
            if tag_name.lower() in self_closing:
                continue
                
            if not is_closing:
                stack.append((tag_name, i + 1))
            else:
                if stack:
                    # try to pop until we match (to forgive small errors like unclosed inline tags)
                    matched_idx = -1
                    for idx in range(len(stack)-1, -1, -1):
                        if stack[idx][0] == tag_name:
                            matched_idx = idx
                            break
                    
                    if matched_idx != -1:
                        # Pop everything up to matched_idx
                        stack = stack[:matched_idx]
                    else:
                        print(f"Warning: Found closing </{tag_name}> at line {i+1} but no matching open.")
        
        if i + 1 == 2038: # Just before </main>
            print(f"Stack at line 2038: {[t[0] + ' (' + str(t[1]) + ')' for t in stack]}")

    if stack:
        print("Unclosed tags remaining at EOF:")
        for tag, line in stack:
            print(f"  <{tag}> opened at line {line}")

if __name__ == '__main__':
    check_jsx('c:\\Users\\amohanra\\OneDrive - The Estée Lauder Companies Inc\\Desktop\\OpenMeta\\frontend\\src\\app\\ProtoApp.tsx')
