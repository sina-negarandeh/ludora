import pandas as pd
import numpy as np

df = pd.read_csv('data/raw/games.csv')
print("Complexity (GameWeight) percentiles:", np.percentile(df['GameWeight'].dropna(), [0, 25, 50, 75, 100]))
print("Playtime (MfgPlaytime) percentiles:", np.percentile(df['MfgPlaytime'].dropna(), [0, 25, 50, 75, 95, 99, 100]))
print("Min Age (MfgAgeRec) percentiles:", np.percentile(df['MfgAgeRec'].dropna(), [0, 25, 50, 75, 100]))
print("Max Players (MaxPlayers) percentiles:", np.percentile(df['MaxPlayers'].dropna(), [0, 25, 50, 75, 95, 100]))
