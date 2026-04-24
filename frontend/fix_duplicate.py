import os

path = os.path.join(
    r"c:\Users\amohanra\OneDrive - The Estée Lauder Companies Inc\Desktop\OpenMeta",
    "frontend", "src", "app", "ProtoApp.tsx"
)

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines before: {len(lines)}")

# Line 774 (0-indexed: 773) is the last good line: "  const [passport, ..."
# Line 775 (0-indexed: 774) starts the garbage: "            <div style=..."
# We need to find where the garbage ends.
# From the analysis, line 963 (0-indexed: 962) has "  const [blast, ..."

# Find the "const [blast" line
blast_line_idx = None
for i, line in enumerate(lines):
    if "const [blast, setBlast]" in line and i > 774:
        blast_line_idx = i
        break

print(f"Found 'blast' line at index {blast_line_idx} (line {blast_line_idx + 1})")
print(f"Will remove lines {775} to {blast_line_idx + 1} (0-indexed: {774} to {blast_line_idx - 1})")

if blast_line_idx:
    # Keep lines 0-773 (up to passport), then skip to blast line
    new_lines = lines[:774] + lines[blast_line_idx:]
    
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"Total lines after: {len(new_lines)}")
    print("SUCCESS: Removed corrupt block")
    
    # Show what's around the join point
    for i in range(770, min(780, len(new_lines))):
        print(f"  {i+1}: {new_lines[i].rstrip()}")
