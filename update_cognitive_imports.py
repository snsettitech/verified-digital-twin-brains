import os

file_path = "backend/routers/cognitive.py"

with open(file_path, "r") as f:
    lines = f.readlines()

new_lines = []
imports_added = False

for line in lines:
    if "from modules.auth_guard import" in line and not imports_added:
        # Update auth_guard import to include verify_twin_ownership
        if "verify_twin_ownership" not in line:
            line = line.replace("require_tenant", "require_tenant, verify_twin_ownership")
            # If verify_twin_ownership was not added (e.g. require_tenant wasn't there), ensure it is
            if "verify_twin_ownership" not in line:
                # Handle case where line is split or different
                # Just append a new import line for safety
                new_lines.append("from modules.auth_guard import verify_twin_ownership\n")
        new_lines.append(line)

        # Add InterviewController imports
        new_lines.append("from modules._core.interview_controller import InterviewController, InterviewStage, INTENT_QUESTIONS\n")
        imports_added = True
    else:
        new_lines.append(line)

# Also need to fix host_policy and spec usage in cognitive_interview
# Scan through function to find where to insert initialization
final_lines = []
in_cognitive_interview = False
policy_inserted = False

for line in new_lines:
    final_lines.append(line)
    if "async def cognitive_interview(" in line:
        in_cognitive_interview = True

    if in_cognitive_interview and "twin = require_twin_access(twin_id, user)" in line and not policy_inserted:
        # Insert policy loading
        final_lines.append("    # Load specialization and policy\n")
        final_lines.append("    spec = get_specialization(twin.get(\"specialization_id\"))\n")
        final_lines.append("    host_policy = _load_host_policy(spec.name)\n")
        policy_inserted = True

with open(file_path, "w") as f:
    f.writelines(final_lines)

print("Imports and definitions updated.")
