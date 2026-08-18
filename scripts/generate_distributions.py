import pandas as pd
import numpy as np
import json
import os

def smooth(y, box_pts):
    box = np.ones(box_pts)/box_pts
    y_smooth = np.convolve(y, box, mode='same')
    return y_smooth

RAW_DATA_THRENJEN_DIR = os.environ.get(
    'RAW_DATA_THRENJEN_DIR',
    'data/raw/kaggle_datasets_threnjen_board-games-database-from-boardgamegeek',
)


def main():
    csv_path = os.path.join(RAW_DATA_THRENJEN_DIR, 'games.csv')
    df = pd.read_csv(csv_path)

    CATEGORIES = [
        'Cat:Thematic', 'Cat:Strategy', 'Cat:War', 'Cat:Family',
        'Cat:CGS', 'Cat:Abstract', 'Cat:Party', 'Cat:Childrens'
    ]

    METRICS = {
        'Complexity': {'col': 'GameWeight', 'min': 0.0, 'max': 5.0, 'bins': 50},
        'Playtime': {'col': 'MfgPlaytime', 'min': 0.0, 'max': 240.0, 'bins': 48},
        'Players': {'col': 'MaxPlayers', 'min': 1.0, 'max': 10.0, 'bins': 10},
        'Min Players': {'col': 'MinPlayers', 'min': 1.0, 'max': 10.0, 'bins': 10},
        'Min Age': {'col': 'MfgAgeRec', 'min': 0.0, 'max': 18.0, 'bins': 18},
    }

    results = {}

    def process_group(group_df, group_name):
        group_results = {}
        for m_name, m_info in METRICS.items():
            col = m_info['col']
            vals = group_df[col].dropna()
            
            # Filter out 0s for weight and playtime which usually mean missing
            if m_name in ['Complexity', 'Playtime']:
                vals = vals[vals > 0]
                
            # clip outliers
            vals = np.clip(vals, m_info['min'], m_info['max'])
            
            hist, bin_edges = np.histogram(vals, bins=m_info['bins'], range=(m_info['min'], m_info['max']))
            
            if len(vals) > 0:
                density = hist / len(vals)
                # smooth continuous metrics slightly to look like bell curves
                if m_name in ['Complexity', 'Playtime']:
                    density = smooth(density, 3)
                
                # normalize density so the peak is exactly 1.0 (easy SVG rendering 0-100% height)
                if np.max(density) > 0:
                    density = density / np.max(density)
                    
                cdf = np.cumsum(hist) / len(vals)
            else:
                density = np.zeros(m_info['bins'])
                cdf = np.zeros(m_info['bins'])
                
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
            
            group_results[m_name] = {
                'x': [round(v, 2) for v in bin_centers],
                'density': [round(v, 4) for v in density],
                'cdf': [round(v, 4) for v in cdf],
                'min': m_info['min'],
                'max': m_info['max']
            }
        results[group_name] = group_results

    # Process Overall
    print("Processing Overall...")
    process_group(df, 'Overall')

    # Process Categories
    for cat in CATEGORIES:
        print(f"Processing {cat}...")
        cat_df = df[df[cat] == 1]
        cat_name = cat.replace('Cat:', '')
        process_group(cat_df, cat_name)

    out_path = os.path.join(os.path.dirname(__file__), '../frontend/public/distributions.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(results, f)
    print(f"Saved to {out_path}")

if __name__ == '__main__':
    main()
