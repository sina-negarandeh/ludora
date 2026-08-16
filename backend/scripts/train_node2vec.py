import networkx as nx
from node2vec import Node2Vec
import os
import pickle

def main():
    base_dir = os.path.join(os.path.dirname(__file__), '../../data/processed')
    graph_path = os.path.join(base_dir, 'node2vec_graph.gpickle')
    
    if not os.path.exists(graph_path):
        print(f"Error: Could not find graph at {graph_path}")
        return
        
    print(f"Loading graph from {graph_path}...")
    with open(graph_path, 'rb') as f:
        G = pickle.load(f)
        
    print(f"Graph loaded. Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
    
    print("Initializing Node2Vec...")
    # Parameters for Node2Vec
    # dimensions: 64 is standard for mid-sized graphs
    # walk_length: 30-80
    # num_walks: 100-200
    # workers: use multiple threads
    # p, q: standard values are 1, 1 for deepwalk equivalence
    n2v = Node2Vec(G, dimensions=64, walk_length=30, num_walks=100, workers=4, p=1, q=1)
    
    print("Training Word2Vec model on walks...")
    # window: 10
    # min_count: 1
    # batch_words: 4
    model = n2v.fit(window=10, min_count=1, batch_words=4)
    
    # Save the model
    model_dir = os.path.join(os.path.dirname(__file__), '../../data/models')
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, 'node2vec.model')
    print(f"Saving trained model to {model_path}...")
    model.save(model_path)
    
    print("Done! You can load this with Word2Vec.load('node2vec.model')")

if __name__ == "__main__":
    main()
