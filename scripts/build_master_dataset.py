import os
import pandas as pd
import json
import ast

# Run from the repo root (matches every other pipeline script — see
# docs/setup/README.md). Override via env var for Docker or any other cwd;
# inside the backend container these must be set explicitly, since
# data/raw/... is not reachable from /app (see docker-compose.yml).
RAW_DATA_THRENJEN_DIR = os.environ.get(
    'RAW_DATA_THRENJEN_DIR',
    'data/raw/kaggle_datasets_threnjen_board-games-database-from-boardgamegeek',
)
RAW_DATA_JVANELTEREN_DIR = os.environ.get(
    'RAW_DATA_JVANELTEREN_DIR',
    'data/raw/kaggle_datasets_jvanelteren_boardgamegeek-reviews',
)
PROCESSED_DATA_DIR = os.environ.get('PROCESSED_DATA_DIR', 'data/processed')

THEME_PREFIX = 'Theme: '  # jvanelteren boardgamefamily namespace prefix
THEME_COL_PREFIX = 'Theme_'  # Threnjen themes.csv column prefix for the same


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


def to_json_string(val):
    """Re-serialize a Python-literal-repr cell (e.g. jvanelteren's poll
    columns) as valid JSON text, so it loads cleanly into a Postgres JSON
    column. Returns None for anything that isn't a parseable list/dict.
    """
    if pd.isna(val):
        return None
    try:
        parsed = ast.literal_eval(val)
    except (ValueError, SyntaxError):
        return None
    return json.dumps(parsed)


def resolve_with_fallback(final_df, primary_series, threnjen_csv_path, usecols_filter=None, name_transform=None):
    """For each game: primary_series's list if non-empty, else a name list
    built from a Threnjen wide one-hot file (BGGId + one binary column per
    entity name), but ONLY reading rows for games that actually need it —
    not the full ~21,925-row file, which matters once files get wide
    (publishers_reduced.csv alone is 1,866 columns).
    """
    needs_fallback_ids = set(final_df.loc[primary_series.apply(len) == 0, 'bgg_id'].astype(int))
    if not needs_fallback_ids or threnjen_csv_path is None:
        return primary_series

    df = pd.read_csv(threnjen_csv_path)
    df = df[df['BGGId'].isin(needs_fallback_ids)]
    entity_cols = [c for c in df.columns if c != 'BGGId' and (usecols_filter is None or usecols_filter(c))]
    long = df.melt(id_vars=['BGGId'], value_vars=entity_cols, var_name='name', value_name='flag')
    long = long[long['flag'] == 1]
    if name_transform:
        long['name'] = long['name'].apply(name_transform)
    fallback_lookup = long.groupby('BGGId')['name'].apply(list).to_dict()

    bgg_ids = final_df['bgg_id'].astype(int).tolist()
    result = [p if p else fallback_lookup.get(bgg_id, []) for bgg_id, p in zip(bgg_ids, primary_series)]
    return pd.Series(result, index=final_df.index)


def extract_relational_data_from_lists(bgg_ids, lists_series, entity_name):
    """Build an entity table + game-mapping table from a Series of
    per-game name lists (already resolved — primary source, fallback, or
    both — by the caller).
    """
    print(f"Extracting relational data for {entity_name}...")
    entity_set = set()
    mappings = []
    for game_id, items in zip(bgg_ids, lists_series):
        for item in items:
            if item:
                entity_set.add(item)
                mappings.append({'game_id': game_id, f'{entity_name}_name': item})

    entities = sorted(entity_set)
    entity_df = pd.DataFrame({'id': range(1, len(entities) + 1), 'name': entities})

    mapping_df = pd.DataFrame(mappings)
    if not mapping_df.empty:
        mapping_df = mapping_df.merge(entity_df, left_on=f'{entity_name}_name', right_on='name', how='left')
        mapping_df = mapping_df[['game_id', 'id']].rename(columns={'id': f'{entity_name}_id'})
    else:
        mapping_df = pd.DataFrame(columns=['game_id', f'{entity_name}_id'])

    return entity_df, mapping_df


def split_family_tag(tag):
    """BGG Family tags are namespaced as "Group: Value" (e.g. "Animals:
    Bears"). A small number (93 of 77,056 instances) carry no namespace at
    all — bucketed under a synthetic "Other" group.
    """
    if ':' in tag:
        group, value = tag.split(':', 1)
        return group.strip(), value.strip()
    return 'Other', tag.strip()


def extract_family_data(bgg_ids, lists_series):
    """Family tags carry a BGG namespace prefix ("Group: Value"). Modeled as
    two levels: families (the 72 groups) and subfamilies (the 4,208 values,
    FK'd to their group) — games link to the leaf level only, since a game
    is never tagged with a bare group in the source data. See
    docs/data/README.md.
    """
    print("Extracting relational data for family...")
    groups = set()
    values = set()  # (group_name, value)
    mappings = []
    for game_id, items in zip(bgg_ids, lists_series):
        for item in items:
            if not item:
                continue
            group_name, value = split_family_tag(item)
            groups.add(group_name)
            values.add((group_name, value))
            mappings.append({'game_id': game_id, 'group_name': group_name, 'value': value})

    sorted_groups = sorted(groups)
    family_df = pd.DataFrame({'id': range(1, len(sorted_groups) + 1), 'name': sorted_groups})
    family_id_by_name = dict(zip(family_df['name'], family_df['id']))

    sorted_values = sorted(values)
    subfamily_df = pd.DataFrame({
        'id': range(1, len(sorted_values) + 1),
        'group_name': [g for g, v in sorted_values],
        'value': [v for g, v in sorted_values],
    })
    subfamily_df['family_id'] = subfamily_df['group_name'].map(family_id_by_name)
    subfamily_df['name'] = subfamily_df['group_name'] + ': ' + subfamily_df['value']
    subfamily_id_by_key = dict(zip(zip(subfamily_df['group_name'], subfamily_df['value']), subfamily_df['id']))
    subfamily_df = subfamily_df[['id', 'family_id', 'value', 'name']]

    mapping_df = pd.DataFrame(mappings)
    if not mapping_df.empty:
        mapping_df['subfamily_id'] = list(
            zip(mapping_df['group_name'], mapping_df['value'])
        )
        mapping_df['subfamily_id'] = mapping_df['subfamily_id'].map(subfamily_id_by_key)
        mapping_df = mapping_df[['game_id', 'subfamily_id']].drop_duplicates()
    else:
        mapping_df = pd.DataFrame(columns=['game_id', 'subfamily_id'])

    return family_df, subfamily_df, mapping_df


def build_game_relations(final_df, column, relation_type, name_to_id):
    """Extract one relation_type's stringified name-list column into
    (game_id, related_name, related_game_id, relation_type) rows.
    related_game_id is null wherever related_name doesn't exact-match
    (case/whitespace-normalized) a known game name in this dataset.
    """
    parsed = final_df[column].apply(parse_stringified_list)
    tmp = pd.DataFrame({'game_id': final_df['bgg_id'], 'related_name': parsed})
    tmp = tmp.explode('related_name')
    tmp = tmp[tmp['related_name'].notna() & (tmp['related_name'] != '')]
    tmp['related_game_id'] = tmp['related_name'].map(
        lambda n: name_to_id.get(str(n).strip().lower())
    )
    tmp['relation_type'] = relation_type
    return tmp[['game_id', 'related_name', 'related_game_id', 'relation_type']]


def main():
    print("Loading datasets...")
    threnjen_df = pd.read_csv(os.path.join(RAW_DATA_THRENJEN_DIR, 'games.csv'))
    new_df = pd.read_csv(os.path.join(RAW_DATA_JVANELTEREN_DIR, 'games_detailed_info2025.csv'))

    print(f"Threnjen rows: {len(threnjen_df)}, 2025 rows: {len(new_df)}")

    new_df.rename(columns={'id': 'BGGId'}, inplace=True)

    assert threnjen_df['BGGId'].is_unique, "BGGId is not unique in Threnjen games.csv"
    assert new_df['BGGId'].is_unique, "BGGId is not unique in jvanelteren games_detailed_info2025.csv"

    master_df = pd.merge(threnjen_df, new_df, on='BGGId', how='outer', suffixes=('_old', '_new'))
    print(f"Merged master rows: {len(master_df)}")

    final_df = pd.DataFrame()
    final_df['bgg_id'] = master_df['BGGId']
    final_df['name'] = master_df['name'].fillna(master_df['Name'])

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

    final_df['avg_rating'] = master_df['average'].fillna(master_df['AvgRating'])
    final_df['bayes_avg_rating'] = master_df['bayesaverage'].fillna(master_df['BayesAvgRating'])
    final_df['game_weight'] = master_df['averageweight'].fillna(master_df['GameWeight'])
    final_df['median_rating'] = master_df['median']
    final_df['stddev_rating'] = master_df['stddev'].fillna(master_df['StdDev'])
    final_df['num_weight_votes'] = master_df['numweights'].fillna(master_df['NumWeightVotes'])
    final_df['num_ratings'] = master_df['usersrated'].fillna(master_df['NumUserRatings'])

    final_df['rank_boardgame'] = master_df['Board Game Rank'].fillna(master_df['Rank:boardgame'])

    final_df['owned_count'] = master_df['owned'].fillna(master_df['NumOwned'])
    final_df['trading_count'] = master_df['trading']
    final_df['wanting_count'] = master_df['wanting'].fillna(master_df['NumWant'])
    final_df['wishing_count'] = master_df['wishing'].fillna(master_df['NumWish'])
    final_df['num_comments'] = master_df['numcomments'].fillna(master_df['NumComments'])

    final_df['kickstarted'] = master_df['Kickstarted']
    final_df['is_reimplementation'] = master_df['IsReimplementation']

    final_df['suggested_num_players'] = master_df['suggested_num_players'].apply(to_json_string)
    final_df['suggested_playerage'] = master_df['suggested_playerage'].apply(to_json_string)
    final_df['suggested_language_dependence'] = master_df['suggested_language_dependence'].apply(to_json_string)

    # Temporarily bring along the stringified arrays needed for relational
    # extraction below; all dropped before the final games CSV is written.
    final_df['boardgamecategory'] = master_df['boardgamecategory']
    final_df['boardgamemechanic'] = master_df['boardgamemechanic']
    final_df['boardgamefamily'] = master_df['boardgamefamily']
    final_df['boardgamedesigner'] = master_df['boardgamedesigner']
    final_df['boardgameartist'] = master_df['boardgameartist']
    final_df['boardgamepublisher'] = master_df['boardgamepublisher']
    final_df['boardgameexpansion'] = master_df['boardgameexpansion']
    final_df['boardgameimplementation'] = master_df['boardgameimplementation']
    final_df['boardgameintegration'] = master_df['boardgameintegration']

    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)

    # --- Subdomains (BGG's rank/leaderboard type — was mislabeled "categories") ---
    subdomain_names = ['Thematic', 'Strategy', 'War', 'Family', 'CGS', 'Abstract', 'Party', 'Childrens']
    subdomain_df = pd.DataFrame({'id': range(1, 9), 'name': subdomain_names})

    subdomain_rank_col = {
        'Thematic': 'Thematic Rank', 'Strategy': 'Strategy Game Rank', 'War': 'War Game Rank',
        'Family': 'Family Game Rank', 'CGS': 'Customizable Rank', 'Abstract': 'Abstract Game Rank',
        'Party': 'Party Game Rank', 'Childrens': "Children's Game Rank",
    }
    game_subdomain_list = []
    for idx, row in master_df.iterrows():
        bgg_id = int(row['BGGId'])
        for sub_id, sub_name in enumerate(subdomain_names, 1):
            has_sub = False
            old_flag_col = f'Cat:{sub_name}'
            if old_flag_col in row and row[old_flag_col] == 1:
                has_sub = True
            rank_col = subdomain_rank_col[sub_name]
            if rank_col in row:
                rank_val = row[rank_col]
                if pd.notna(rank_val) and str(rank_val).lower() not in ('not ranked', 'nan', ''):
                    has_sub = True
            if has_sub:
                game_subdomain_list.append({'game_id': bgg_id, 'subdomain_id': sub_id})
    game_subdomain_df = pd.DataFrame(game_subdomain_list).drop_duplicates()

    # --- Categories (BGG's real boardgamecategory field — was mislabeled "themes") ---
    # Primary: jvanelteren boardgamecategory. Fallback (for the ~428 games
    # with no jvanelteren row): Threnjen's non-"Theme_" themes.csv columns,
    # then Threnjen's subcategories.csv — both verified as the same BGG
    # Category taxonomy, not a separate concept. See docs/data/README.md.
    category_primary = final_df['boardgamecategory'].apply(parse_stringified_list)
    category_lists = resolve_with_fallback(
        final_df, category_primary,
        os.path.join(RAW_DATA_THRENJEN_DIR, 'themes.csv'),
        usecols_filter=lambda c: not c.startswith(THEME_COL_PREFIX),
    )
    category_lists = resolve_with_fallback(
        final_df, category_lists,
        os.path.join(RAW_DATA_THRENJEN_DIR, 'subcategories.csv'),
    )
    cat_df, game_cat_df = extract_relational_data_from_lists(final_df['bgg_id'], category_lists, 'category')

    # --- Themes (BGG Family's "Theme:" group only — genuinely new, never sourced before) ---
    theme_primary = final_df['boardgamefamily'].apply(
        lambda v: [i[len(THEME_PREFIX):] for i in parse_stringified_list(v) if i.startswith(THEME_PREFIX)]
    )
    theme_lists = resolve_with_fallback(
        final_df, theme_primary,
        os.path.join(RAW_DATA_THRENJEN_DIR, 'themes.csv'),
        usecols_filter=lambda c: c.startswith(THEME_COL_PREFIX),
        name_transform=lambda n: n[len(THEME_COL_PREFIX):],
    )
    theme_df, game_theme_df = extract_relational_data_from_lists(final_df['bgg_id'], theme_lists, 'theme')

    # --- Families (BGG Family, boardgamefamily — the full field, all 72
    # namespaces including Theme:, which is also separately extracted above
    # into its own table today; consolidating the two is a later decision) ---
    family_lists = final_df['boardgamefamily'].apply(parse_stringified_list)
    family_df, subfamily_df, game_subfamily_df = extract_family_data(final_df['bgg_id'], family_lists)

    # --- Mechanics / Designers / Artists / Publishers (unchanged concept, now with Threnjen fallback) ---
    mech_primary = final_df['boardgamemechanic'].apply(parse_stringified_list)
    mech_lists = resolve_with_fallback(final_df, mech_primary, os.path.join(RAW_DATA_THRENJEN_DIR, 'mechanics.csv'))
    mech_df, game_mech_df = extract_relational_data_from_lists(final_df['bgg_id'], mech_lists, 'mechanic')

    des_primary = final_df['boardgamedesigner'].apply(parse_stringified_list)
    des_lists = resolve_with_fallback(
        final_df, des_primary, os.path.join(RAW_DATA_THRENJEN_DIR, 'designers_reduced.csv'),
        usecols_filter=lambda c: c != 'Low-Exp Designer',
    )
    des_df, game_des_df = extract_relational_data_from_lists(final_df['bgg_id'], des_lists, 'designer')

    art_primary = final_df['boardgameartist'].apply(parse_stringified_list)
    art_lists = resolve_with_fallback(
        final_df, art_primary, os.path.join(RAW_DATA_THRENJEN_DIR, 'artists_reduced.csv'),
        usecols_filter=lambda c: c != 'Low-Exp Artist',
    )
    art_df, game_art_df = extract_relational_data_from_lists(final_df['bgg_id'], art_lists, 'artist')

    pub_primary = final_df['boardgamepublisher'].apply(parse_stringified_list)
    pub_lists = resolve_with_fallback(
        final_df, pub_primary, os.path.join(RAW_DATA_THRENJEN_DIR, 'publishers_reduced.csv'),
        usecols_filter=lambda c: c != 'Low-Exp Publisher',
    )
    pub_df, game_pub_df = extract_relational_data_from_lists(final_df['bgg_id'], pub_lists, 'publisher')

    # Save relational metadata
    subdomain_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_subdomains.csv'), index=False)
    game_subdomain_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_game_subdomains.csv'), index=False)

    cat_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_categories.csv'), index=False)
    game_cat_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_game_categories.csv'), index=False)

    theme_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_themes.csv'), index=False)
    game_theme_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_game_themes.csv'), index=False)

    family_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_families.csv'), index=False)
    subfamily_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_subfamilies.csv'), index=False)
    game_subfamily_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_game_subfamilies.csv'), index=False)

    mech_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_mechanics.csv'), index=False)
    game_mech_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_game_mechanics.csv'), index=False)

    des_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_designers.csv'), index=False)
    game_des_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_game_designers.csv'), index=False)

    art_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_artists.csv'), index=False)
    game_art_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_game_artists.csv'), index=False)

    pub_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_publishers.csv'), index=False)
    game_pub_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_game_publishers.csv'), index=False)

    print("Saved all relational metadata to", PROCESSED_DATA_DIR)
    print(f"  subdomains: {len(subdomain_df)} values, {len(game_subdomain_df)} game links")
    print(f"  categories: {len(cat_df)} values, {len(game_cat_df)} game links")
    print(f"  themes: {len(theme_df)} values, {len(game_theme_df)} game links")
    print(f"  families: {len(family_df)} groups, {len(subfamily_df)} values, {len(game_subfamily_df)} game links")
    print(f"  mechanics: {len(mech_df)} values, {len(game_mech_df)} game links")
    print(f"  designers: {len(des_df)} values, {len(game_des_df)} game links")
    print(f"  artists: {len(art_df)} values, {len(game_art_df)} game links")
    print(f"  publishers: {len(pub_df)} values, {len(game_pub_df)} game links")

    # --- Game relations (expansions/implementations/integrations) ---
    valid_names = final_df.dropna(subset=['name'])
    name_to_id = dict(zip(valid_names['name'].str.strip().str.lower(), valid_names['bgg_id']))

    relations_df = pd.concat([
        build_game_relations(final_df, 'boardgameexpansion', 'expansion', name_to_id),
        build_game_relations(final_df, 'boardgameimplementation', 'implementation', name_to_id),
        build_game_relations(final_df, 'boardgameintegration', 'integration', name_to_id),
    ], ignore_index=True)
    # related_game_id must write as a clean integer or empty string, not
    # "2092.0" — Postgres COPY rejects float-formatted text for an int column.
    relations_df['related_game_id'] = relations_df['related_game_id'].astype('Int64')
    relations_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_game_relations.csv'), index=False)

    resolved = int(relations_df['related_game_id'].notna().sum())
    total = len(relations_df)
    pct = (resolved / total * 100) if total else 0.0
    print(f"Game relations: {total} rows, {resolved} resolved to a known game ({pct:.1f}%)")

    # Drop the raw stringified columns from final games csv to keep it normalized
    final_df.drop(columns=[
        'boardgamecategory', 'boardgamemechanic', 'boardgamefamily',
        'boardgamedesigner', 'boardgameartist', 'boardgamepublisher',
        'boardgameexpansion', 'boardgameimplementation', 'boardgameintegration',
    ], inplace=True)

    final_df['rank_boardgame'] = pd.to_numeric(final_df['rank_boardgame'], errors='coerce')

    missing_name = int(final_df['name'].isna().sum())
    if missing_name:
        print(f"WARNING: {missing_name} games have no name after merge")

    final_df.to_csv(os.path.join(PROCESSED_DATA_DIR, 'master_games.csv'), index=False)
    print(f"Saved final master dataset to {os.path.join(PROCESSED_DATA_DIR, 'master_games.csv')} ({len(final_df)} games)")

if __name__ == "__main__":
    main()
