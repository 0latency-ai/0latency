# Fix the params tuple - local_embedding was inserted in wrong place

with open('storage_multitenant.py', 'r') as f:
    lines = f.readlines()

# Find the params tuple and fix it
in_params = False
fixed_lines = []
for i, line in enumerate(lines):
    if 'params = (' in line:
        in_params = True
        fixed_lines.append(line)
    elif in_params and 'local_embedding,' in line and 'embedding,' not in lines[i+1]:
        # Skip this misplaced local_embedding
        continue
    elif in_params and 'embedding,' in line and 'memory.get' not in line:
        # This is the main embedding line - add local_embedding after it
        fixed_lines.append(line)
        fixed_lines.append('        local_embedding,\n')
    elif in_params and ')' in line and '(' not in line:
        # End of params tuple
        in_params = False
        fixed_lines.append(line)
    else:
        fixed_lines.append(line)

with open('storage_multitenant.py', 'w') as f:
    f.writelines(fixed_lines)

print('Fixed params tuple')
