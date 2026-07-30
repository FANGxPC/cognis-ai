import json
import os

all_node_ids = set()
all_q_ids = set()

def dict_raise_on_duplicates(ordered_pairs):
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            print(f"Error: Duplicate key '{k}' found in JSON!")
        d[k] = v
    return d

def load_json(path):
    with open(path) as f:
        return json.load(f, object_pairs_hook=dict_raise_on_duplicates)

def check_graph_and_questions(graph_path, questions_path):
    print(f"Checking {graph_path} and {questions_path}")
    
    graph_data = load_json(graph_path)
    questions_data = load_json(questions_path)
        
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    
    node_ids = set()
    for node in nodes:
        if node["id"] in node_ids:
            print(f"Error: Duplicate node id '{node['id']}'")
        node_ids.add(node["id"])
        all_node_ids.add(node["id"])
        
        # Check required fields
        for field in ["id", "label", "description", "order"]:
            if field not in node:
                print(f"Error: Node {node.get('id')} is missing field '{field}'")
                
    node_orders = {node["id"]: node["order"] for node in nodes}
    
    # 1. Check edges (dependencies)
    adj = {node_id: [] for node_id in node_ids}
    for edge in edges:
        from_id = edge["from"]
        to_id = edge["to"]
        if from_id not in node_ids:
            print(f"Error: Edge from {from_id} not found in nodes.")
        if to_id not in node_ids:
            print(f"Error: Edge to {to_id} not found in nodes.")
        if from_id in node_ids and to_id in node_ids:
            adj[from_id].append(to_id)
            if node_orders[from_id] >= node_orders[to_id]:
                print(f"Logical Error: Edge {from_id} (order {node_orders[from_id]}) -> {to_id} (order {node_orders[to_id]}), but prereq must have lower order!")
            
    # Check cycles
    visited = {}
    def dfs(u):
        visited[u] = 1 # visiting
        for v in adj.get(u, []):
            if visited.get(v) == 1:
                print(f"Error: Cycle detected involving {u} -> {v}")
            elif visited.get(v) != 2:
                dfs(v)
        visited[u] = 2 # visited
        
    for node in node_ids:
        if node not in visited:
            dfs(node)
            
    # 2. Check for missing questions or missing nodes
    for node_id in node_ids:
        if node_id not in questions_data:
            print(f"Warning: Node '{node_id}' has no questions in {questions_path}")
            
    q_ids = set()
    for topic_id, questions in questions_data.items():
        if topic_id not in node_ids:
            print(f"Error: Question topic '{topic_id}' has no corresponding node in {graph_path}")
            
        for q in questions:
            if not q.get('question'):
                print(f"Error: Question {q.get('id')} missing 'question' text")
            elif not q.get('question').strip().endswith('?'):
                print(f"Warning: Question {q.get('id')} does not end with '?' ({q.get('question')})")
                
            if not q.get('explanation'):
                print(f"Error: Question {q.get('id')} missing 'explanation'")
            
            q_id = q.get('id')
            if q_id in q_ids:
                print(f"Error: Duplicate question id '{q_id}'")
            q_ids.add(q_id)
            all_q_ids.add(q_id)
            
            correct = q.get("correct_answer")
            choices = q.get("choices", {})
            if len(choices) != 4:
                print(f"Error: Question {q_id} does not have exactly 4 choices (has {len(choices)})")
            if correct not in choices:
                print(f"Error in {topic_id} q {q.get('id')}: correct_answer '{correct}' not in choices {list(choices.keys())}")

def check_profiles(profiles_path):
    print(f"Checking {profiles_path}")
    with open(profiles_path) as f:
        profiles = json.load(f).get("profiles", [])
    
    for profile in profiles:
        name = profile.get("name")
        if profile.get("matched_node") and profile.get("matched_node") not in all_node_ids:
            print(f"Error in profile {name}: matched_node '{profile.get('matched_node')}' not found.")
            
        for node_id in profile.get("traversal_path", []):
            if node_id not in all_node_ids:
                print(f"Error in profile {name}: traversal_path contains unknown node '{node_id}'")
                
        for node_id in profile.get("mastery", {}).keys():
            if node_id not in all_node_ids:
                print(f"Error in profile {name}: mastery contains unknown node '{node_id}'")
                
        root = profile.get("root_cause_node")
        if root and root not in all_node_ids:
            print(f"Error in profile {name}: root_cause_node '{root}' not found.")
            
        for topic, qlist in profile.get("asked_questions", {}).items():
            if topic not in all_node_ids:
                print(f"Error in profile {name}: asked_questions topic '{topic}' not found.")
            for q_id in qlist:
                if q_id not in all_q_ids:
                    print(f"Error in profile {name}: asked_questions references unknown q_id '{q_id}'")

if __name__ == '__main__':
    base_dir = '/home/fang/Downloads/prereq-sleuth-frontend (1)/prereq-sleuth-frontend/backend/data'
    ds_g = os.path.join(base_dir, 'data_structures_graph.json')
    ds_q = os.path.join(base_dir, 'data_structures_questions.json')
    la_g = os.path.join(base_dir, 'linear_algebra_graph.json')
    la_q = os.path.join(base_dir, 'linear_algebra_questions.json')
    m_g = os.path.join(base_dir, 'graph.json')
    m_q = os.path.join(base_dir, 'questions.json')
    
    check_graph_and_questions(ds_g, ds_q)
    check_graph_and_questions(la_g, la_q)
    check_graph_and_questions(m_g, m_q)
    
    check_profiles(os.path.join(base_dir, 'demo_profiles.json'))
