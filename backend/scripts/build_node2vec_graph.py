import networkx as nx
import pandas as pd
import os
import pickle

def main():
    print("Building Heterogeneous Graph for Node2Vec...")
    
    base_dir = os.path.join(os.path.dirname(__file__), '../../data/processed')
    
    if not os.path.exists(base_dir):
        print(f"Error: {base_dir} does not exist.")
        return
        
    G = nx.Graph()
    
    # 1. Load Games
    print("Loading games...")
    games_df = pd.read_csv(os.path.join(base_dir, 'master_games.csv'))
    for _, row in games_df.iterrows():
        bgg_id = int(row['bgg_id'])
        G.add_node(f"Game_{bgg_id}", type="Game", name=row['name'])
        
    # 2. Add relational edges
    relations = [
        ('master_game_themes.csv', 'theme_id', 'Theme'),
        ('master_game_mechanics.csv', 'mechanic_id', 'Mechanic'),
        ('master_game_categories.csv', 'category_id', 'Category'),
        ('master_game_designers.csv', 'designer_id', 'Designer'),
        ('master_game_artists.csv', 'artist_id', 'Artist'),
        ('master_game_publishers.csv', 'publisher_id', 'Publisher')
    ]
    
    for filename, id_col, node_type in relations:
        filepath = os.path.join(base_dir, filename)
        if not os.path.exists(filepath):
            print(f"Skipping {node_type} - {filename} not found.")
            continue
            
        print(f"Adding {node_type} edges...")
        df = pd.read_csv(filepath)
        edges_added = 0
        for _, row in df.iterrows():
            game_node = f"Game_{int(row['game_id'])}"
            attr_node = f"{node_type}_{int(row[id_col])}"
            
            # Ensure the attribute node exists with correct type
            if not G.has_node(attr_node):
                G.add_node(attr_node, type=node_type)
                
            G.add_edge(game_node, attr_node)
            edges_added += 1
            
        print(f"  Added {edges_added} edges for {node_type}.")
        
    print(f"Graph Construction Complete!")
    print(f"Total Nodes: {G.number_of_nodes()}")
    print(f"Total Edges: {G.number_of_edges()}")
    
    out_path = os.path.join(base_dir, 'node2vec_graph.gpickle')
    print(f"Saving graph to {out_path}...")
    with open(out_path, 'wb') as f:
        pickle.dump(G, f)
        
    print("Done!")

if __name__ == "__main__":
    main()
