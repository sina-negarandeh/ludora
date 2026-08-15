import os
import pandas as pd
import json
import ast

def parse_stringified_list(val):
    if pd.isna(val):
        return []
    try:
        # Often lists in CSVs look like "['A', 'B']"
        parsed = ast.literal_eval(val)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed]
        return []
    except (ValueError, SyntaxError):
        # Fallback if it's just a comma separated string
        return [x.strip() for x in str(val).split(',')]

def extract_relational_data(df, column_name, entity_name):
    print(f"Extracting relational data for {entity_name} from {column_name}...")
    
    entity_set = set()
    mappings = []
    
    for idx, row in df.iterrows():
        game_id = row['bgg_id']
        items = parse_stringified_list(row[column_name])
        for item in items:
            if item:
                entity_set.add(item)
                mappings.append({'game_id': game_id, f'{entity_name}_name': item})
                
    # Create entity dataframe with IDs
    entities = sorted(list(entity_set))
    entity_df = pd.DataFrame({
        'id': range(1, len(entities) + 1),
        'name': entities
    })
    
    # Create mapping dataframe
    mapping_df = pd.DataFrame(mappings)
    if not mapping_df.empty:
        mapping_df = mapping_df.merge(entity_df, left_on=f'{entity_name}_name', right_on='name', how='left')
        mapping_df = mapping_df[['game_id', 'id']].rename(columns={'id': f'{entity_name}_id'})
    else:
        mapping_df = pd.DataFrame(columns=['game_id', f'{entity_name}_id'])
        
    return entity_df, mapping_df

def main():
    print("Loading datasets...")
    # Load Threnjen dataset
    threnjen_df = pd.read_csv('../data/raw/games.csv')
    
    # Load 2025 dataset
    new_df = pd.read_csv('../data/raw/reviews/games_detailed_info2025.csv')
    
    print(f"Threnjen rows: {len(threnjen_df)}, 2025 rows: {len(new_df)}")
    
    # Standardize primary key for merge
    new_df.rename(columns={'id': 'BGGId'}, inplace=True)
    
    # Outer merge
    master_df = pd.merge(threnjen_df, new_df, on='BGGId', how='outer', suffixes=('_old', '_new'))
    
    print(f"Merged master rows: {len(master_df)}")
    
    # Define explicitly which columns to keep according to the field-level policy
    final_df = pd.DataFrame()
    final_df['bgg_id'] = master_df['BGGId']
    final_df['name'] = master_df['name'].fillna(master_df['Name'])
    
    # Prefer 2025 dataset for descriptions and core metrics
    final_df['description'] = master_df['description'].fillna(master_df['Description'])
    final_df['year_published'] = master_df['yearpublished'].fillna(master_df['YearPublished'])
    final_df['min_players'] = master_df['minplayers'].fillna(master_df['MinPlayers'])
    final_df['max_players'] = master_df['maxplayers'].fillna(master_df['MaxPlayers'])
    final_df['mfg_playtime'] = master_df['playingtime'].fillna(master_df['MfgPlaytime'])
    final_df['min_playtime'] = master_df['minplaytime'].fillna(master_df['ComMinPlaytime'])
    final_df['max_playtime'] = master_df['maxplaytime'].fillna(master_df['ComMaxPlaytime'])
    final_df['min_age'] = master_df['minage'].fillna(master_df['MfgAgeRec'])
    final_df['thumbnail_url'] = master_df['thumbnail']
    final_df['image_url'] = master_df['image'].fillna(master_df['ImagePath'])
    
    # Community Ratings from 2025
    final_df['avg_rating'] = master_df['average'].fillna(master_df['AvgRating'])
    final_df['bayes_avg_rating'] = master_df['bayesaverage'].fillna(master_df['BayesAvgRating'])
    final_df['game_weight'] = master_df['averageweight'].fillna(master_df['GameWeight'])
    final_df['median_rating'] = master_df['median']
    final_df['stddev_rating'] = master_df['stddev'].fillna(master_df['StdDev'])
    final_df['num_weight_votes'] = master_df['numweights'].fillna(master_df['NumWeightVotes'])
    final_df['num_ratings'] = master_df['usersrated'].fillna(master_df['NumUserRatings'])
    
    # Ranks
    final_df['rank_boardgame'] = master_df['Board Game Rank'].fillna(master_df['Rank:boardgame'])
    
    # Community Engagement from 2025
    final_df['owned_count'] = master_df['owned'].fillna(master_df['NumOwned'])
    final_df['trading_count'] = master_df['trading']
    final_df['wanting_count'] = master_df['wanting'].fillna(master_df['NumWant'])
    final_df['wishing_count'] = master_df['wishing'].fillna(master_df['NumWish'])
    final_df['num_comments'] = master_df['numcomments'].fillna(master_df['NumComments'])
    
    # Threnjen Exclusives
    final_df['language_ease'] = master_df['LanguageEase']
    final_df['best_players'] = master_df['BestPlayers']
    final_df['good_players'] = master_df['GoodPlayers']
    final_df['com_age_rec'] = master_df['ComAgeRec']
    final_df['kickstarted'] = master_df['Kickstarted']
    final_df['is_reimplementation'] = master_df['IsReimplementation']
    
    # Temporarily bring along the stringified arrays to parse relational tables
    final_df['boardgamecategory'] = master_df['boardgamecategory']
    final_df['boardgamemechanic'] = master_df['boardgamemechanic']
    final_df['boardgamedesigner'] = master_df['boardgamedesigner']
    final_df['boardgameartist'] = master_df['boardgameartist']
    final_df['boardgamepublisher'] = master_df['boardgamepublisher']

    # Make processed directory
    os.makedirs('../data/processed', exist_ok=True)
    
    # Extract Relational Metadata
    # Rebuild Categories to strictly use the 8 canonical domains
    cat_names = ['Thematic', 'Strategy', 'War', 'Family', 'CGS', 'Abstract', 'Party', 'Childrens']
    cat_df = pd.DataFrame({'id': range(1, 9), 'name': cat_names})
    
    cat_to_rank_col = {
        'Thematic': 'Thematic Rank',
        'Strategy': 'Strategy Game Rank',
        'War': 'War Game Rank',
        'Family': 'Family Game Rank',
        'CGS': 'Customizable Rank',
        'Abstract': 'Abstract Game Rank',
        'Party': 'Party Game Rank',
        'Childrens': "Children's Game Rank"
    }
    
    game_cat_list = []
    for idx, row in master_df.iterrows():
        bgg_id = int(row['BGGId'])
        for cat_id, cat_name in enumerate(cat_names, 1):
            has_cat = False
            
            # Check old dataset flag
            old_cat_col = f'Cat:{cat_name}'
            if old_cat_col in row and row[old_cat_col] == 1:
                has_cat = True
                
            # Check new dataset rank
            new_rank_col = cat_to_rank_col[cat_name]
            if new_rank_col in row:
                rank_val = row[new_rank_col]
                if pd.notna(rank_val) and str(rank_val).lower() not in ('not ranked', 'nan', ''):
                    has_cat = True
                    
            if has_cat:
                game_cat_list.append({'game_id': bgg_id, 'category_id': cat_id})
                
    game_cat_df = pd.DataFrame(game_cat_list).drop_duplicates()
    
    theme_df, game_theme_df = extract_relational_data(final_df, 'boardgamecategory', 'theme')
    mech_df, game_mech_df = extract_relational_data(final_df, 'boardgamemechanic', 'mechanic')
    des_df, game_des_df = extract_relational_data(final_df, 'boardgamedesigner', 'designer')
    art_df, game_art_df = extract_relational_data(final_df, 'boardgameartist', 'artist')
    pub_df, game_pub_df = extract_relational_data(final_df, 'boardgamepublisher', 'publisher')
    
    # Save Relational Metadata
    cat_df.to_csv('../data/processed/master_categories.csv', index=False)
    game_cat_df.to_csv('../data/processed/master_game_categories.csv', index=False)
    
    theme_df.to_csv('../data/processed/master_themes.csv', index=False)
    game_theme_df.to_csv('../data/processed/master_game_themes.csv', index=False)
    
    mech_df.to_csv('../data/processed/master_mechanics.csv', index=False)
    game_mech_df.to_csv('../data/processed/master_game_mechanics.csv', index=False)
    
    des_df.to_csv('../data/processed/master_designers.csv', index=False)
    game_des_df.to_csv('../data/processed/master_game_designers.csv', index=False)
    
    art_df.to_csv('../data/processed/master_artists.csv', index=False)
    game_art_df.to_csv('../data/processed/master_game_artists.csv', index=False)
    
    pub_df.to_csv('../data/processed/master_publishers.csv', index=False)
    game_pub_df.to_csv('../data/processed/master_game_publishers.csv', index=False)
    
    print("Saved all relational metadata to data/processed/")
    
    # Drop the raw stringified columns from final games csv to keep it normalized
    final_df.drop(columns=[
        'boardgamecategory', 'boardgamemechanic', 'boardgamedesigner', 
        'boardgameartist', 'boardgamepublisher'
    ], inplace=True)
    
    # Clean up ranks (replace string "Not Ranked" with NaN, convert to Int)
    final_df['rank_boardgame'] = pd.to_numeric(final_df['rank_boardgame'], errors='coerce')
    
    # Save the master games dataset
    final_df.to_csv('../data/processed/master_games.csv', index=False)
    print("Saved final master dataset to data/processed/master_games.csv")

if __name__ == "__main__":
    main()
