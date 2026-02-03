import os

file_path = "backend/routers/cognitive.py"

with open(file_path, "r") as f:
    lines = f.readlines()

# 1. Add imports
import_lines = [
    "import os\n",
    "import fnmatch\n"
]

# Insert imports after "import json"
new_lines = []
for line in lines:
    new_lines.append(line)
    if "import json" in line:
        new_lines.extend(import_lines)

# 2. Define helper function
helper_func = """
def _load_ontology_data(spec_name: str) -> Dict[str, Any]:
    \"\"\"Load clusters and required nodes from specialization ontology.\"\"\"
    from pathlib import Path

    ontology_data = {
        "clusters": [],
        "required_nodes": []
    }

    try:
        # Construct path: backend/modules/specializations/{spec_name}/ontology
        backend_base = Path(__file__).parent.parent
        ontology_path = backend_base / "modules" / "specializations" / spec_name / "ontology"

        if ontology_path.exists():
            # Load all pack files
            for filename in os.listdir(ontology_path):
                if filename.endswith("_pack.json"):
                    try:
                        with (ontology_path / filename).open("r", encoding="utf-8") as f:
                            pack = json.load(f)
                            # Extend clusters and required nodes
                            ontology_data["clusters"].extend(pack.get("clusters", []))
                            ontology_data["required_nodes"].extend(pack.get("required_nodes", []))
                    except Exception as e:
                        print(f"Warning: Failed to load ontology pack {filename}: {e}")

    except Exception as e:
        print(f"Warning: Could not load ontology data: {e}")

    return ontology_data

"""

# 3. Replace get_cognitive_graph
new_graph_func = """@router.get("/cognitive/graph/{twin_id}")
async def get_cognitive_graph(twin_id: str, user=Depends(require_tenant)):
    \"\"\"
    Get the current cognitive graph state for a twin.

    Returns:
        - nodes: List of cognitive graph nodes
        - edges: List of cognitive graph edges
        - clusters: Cluster completion percentages
    \"\"\"
    require_twin_access(twin_id, user)

    # 1. Fetch graph data
    nodes = []
    edges = []
    try:
        nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 1000}).execute()
        edges_res = supabase.rpc("get_edges_system", {"t_id": twin_id, "limit_val": 1000}).execute()
        nodes = nodes_res.data or []
        edges = edges_res.data or []
    except Exception as e:
        print(f"Error fetching graph: {e}")

    # 2. Get Specialization & Ontology
    # Use default/env specialization as fallback
    spec = get_specialization()
    ontology = _load_ontology_data(spec.name)

    # 3. Calculate Cluster Completion
    cluster_stats = {}

    clusters = ontology.get("clusters") or []
    required_nodes = ontology.get("required_nodes") or []

    # Map required nodes to clusters
    for cluster in clusters:
        c_id = cluster.get("cluster_id")
        c_patterns = cluster.get("node_types", [])

        # Find required nodes for this cluster
        c_required = []
        for req in required_nodes:
            r_type = req.get("node_type", "")
            if any(fnmatch.fnmatch(r_type, pat) for pat in c_patterns):
                c_required.append(r_type)

        # Count matching nodes in graph
        found_required = 0
        for r_type in c_required:
            if any(n.get("type") == r_type for n in nodes):
                found_required += 1

        # Calculate completion
        completion = 0.0
        if c_required:
            completion = found_required / len(c_required)

        # Count total nodes for this cluster
        total_cluster_nodes = 0
        for node in nodes:
            n_type = node.get("type", "")
            if any(fnmatch.fnmatch(n_type, pat) for pat in c_patterns):
                total_cluster_nodes += 1

        cluster_stats[c_id] = {
            "completion": round(completion, 2),
            "node_count": total_cluster_nodes,
            "label": cluster.get("label", c_id.title())
        }

    # Fallback if no clusters found
    if not cluster_stats:
        cluster_stats = {
            "knowledge": {"completion": 0.0, "node_count": len(nodes), "label": "Knowledge"}
        }

    return {
        "nodes": nodes,
        "edges": edges,
        "clusters": cluster_stats,
    }
"""

# Reconstruct file content
final_lines = []
skip = False
inserted_helper = False

for line in new_lines:
    if "@router.get(\"/cognitive/graph/{twin_id}\")" in line:
        if not inserted_helper:
            final_lines.append(helper_func)
            inserted_helper = True
        final_lines.append(new_graph_func)
        skip = True

    if skip:
        # Stop skipping when we hit the next function or end of file
        # The next function starts with @ or def or class
        # But we need to be careful not to skip too much
        # The existing function ends before "class ApproveRequest"
        if "class ApproveRequest" in line:
            skip = False
            final_lines.append(line)
    else:
        final_lines.append(line)

with open(file_path, "w") as f:
    f.writelines(final_lines)

print("File updated successfully.")
