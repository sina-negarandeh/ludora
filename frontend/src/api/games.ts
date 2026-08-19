import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_URL,
});

export interface PlayerCountPollResult {
  '@value': string;
  '@numvotes': string;
}

export interface PlayerCountPoll {
  '@numplayers': string;
  result: PlayerCountPollResult[];
}

export interface AgePollResult {
  '@value': string;
  '@numvotes': string;
}

export interface Game {
  bgg_id: number;
  name: string;
  description: string;
  year_published: number;
  game_weight: number;
  avg_rating: number;
  min_players: number;
  max_players: number;
  mfg_playtime: number;
  min_playtime?: number;
  max_playtime?: number;
  min_age: number;
  image_path?: string;
  rank?: number;
  num_ratings?: number;
  num_comments?: number;
  rating_distribution?: number[];
  subdomain_ranks?: Record<string, number>;
  suggested_num_players?: PlayerCountPoll[];
  suggested_playerage?: AgePollResult[];
  subdomains: string[];
  categories: string[];
  themes: string[];
  families: string[];
  mechanics: string[];
  designers: string[];
  publishers: string[];
  artists: string[];
  customer_summary?: string;
}

export interface Review {
  id: number;
  user: string;
  rating?: number;
  comment?: string;
}

export interface PaginatedReviews {
  total: number;
  language_breakdown?: Record<string, number>;
  rating_breakdown?: { positive: number; mixed: number; negative: number };
  items: Review[];
}

export interface PaginatedGames {
  total: number;
  items: Game[];
}

export interface GameQuery {
  query?: string;
  subdomains?: string[];
  categories?: string[];
  themes?: string[];
  families?: string[];
  mechanics?: string[];
  designers?: string[];
  artists?: string[];
  publishers?: string[];
  exact_players?: number;
  min_players?: number;
  max_players?: number;
  min_weight?: number;
  max_weight?: number;
  min_playtime?: number;
  max_playtime?: number;
  min_year?: number;
  max_year?: number;
  sort_by?: string;
  order?: string;
  skip?: number;
  limit?: number;
}

export const fetchGames = async (gameQuery: GameQuery = {}) => {
  const params = new URLSearchParams();
  
  // Set default pagination
  params.append('skip', (gameQuery.skip ?? 0).toString());
  params.append('limit', (gameQuery.limit ?? 50).toString());
  
  if (gameQuery.sort_by) params.append('sort_by', gameQuery.sort_by);
  if (gameQuery.order) params.append('order', gameQuery.order);
  
  Object.entries(gameQuery).forEach(([key, value]) => {
    if (['skip', 'limit', 'sort_by', 'order'].includes(key)) return;
    
    if (value !== undefined && value !== null && value !== '') {
      if (Array.isArray(value)) {
        value.forEach(v => params.append(key, v.toString()));
      } else {
        params.append(key, value.toString());
      }
    }
  });

  const { data } = await apiClient.get<PaginatedGames>('/api/games', { params });
  return data;
};

export const fetchGame = async (bgg_id: number): Promise<Game> => {
  const { data } = await apiClient.get<Game>(`/api/games/${bgg_id}`);
  return data;
};

export const fetchCategories = async (): Promise<string[]> => {
  const { data } = await apiClient.get<string[]>('/api/categories');
  return data;
};

export interface SubdomainMetadata {
  id: number;
  name: string;
  game_count: number;
}

export const fetchSubdomains = async (): Promise<SubdomainMetadata[]> => {
  const { data } = await apiClient.get<SubdomainMetadata[]>('/api/subdomains');
  return data;
};

export interface ThemeMetadata {
  id: number;
  name: string;
  game_count: number;
}

export const fetchThemes = async (): Promise<ThemeMetadata[]> => {
  const { data } = await apiClient.get<ThemeMetadata[]>('/api/themes');
  return data;
};

export interface SubfamilyMetadata {
  id: number;
  value: string;
  name: string;
  game_count: number;
}

export interface FamilyGroupMetadata {
  group: string;
  values: SubfamilyMetadata[];
}

export const fetchFamilies = async (): Promise<FamilyGroupMetadata[]> => {
  const { data } = await apiClient.get<FamilyGroupMetadata[]>('/api/families');
  return data;
};

export const fetchMechanics = async (): Promise<string[]> => {
  const { data } = await apiClient.get<string[]>('/api/mechanics');
  return data;
};

export const fetchDesigners = async (): Promise<string[]> => {
  const { data } = await apiClient.get<string[]>('/api/designers');
  return data;
};

export const fetchPublishers = async (): Promise<string[]> => {
  const { data } = await apiClient.get<string[]>('/api/publishers');
  return data;
};

export const fetchArtists = async (): Promise<string[]> => {
  const { data } = await apiClient.get<string[]>('/api/artists');
  return data;
};

export interface SearchQueryPayload {
  q: string;
  mode: 'lexical' | 'semantic' | 'hybrid';
  filters?: {
    subdomains?: string[];
    categories?: string[];
    themes?: string[];
    families?: string[];
    mechanics?: string[];
    designers?: string[];
    artists?: string[];
    publishers?: string[];
    exact_players?: number;
    min_players?: number;
    max_players?: number;
    min_weight?: number;
    max_weight?: number;
    min_playtime?: number;
    max_playtime?: number;
    min_year?: number;
    max_year?: number;
  };
}

export interface SearchDebug {
  lexical_rank?: number;
  semantic_rank?: number;
  rrf_score: number;
}

export interface SearchResult {
  game: Game;
  score: number;
  debug: SearchDebug;
}

export interface PaginatedSearchResults {
  total: number;
  items: SearchResult[];
}

export const fetchSearch = async (
  query: SearchQueryPayload,
  skip: number = 0,
  limit: number = 24
): Promise<PaginatedSearchResults> => {
  const { data } = await apiClient.post<PaginatedSearchResults>(
    '/api/search',
    query,
    { params: { skip, limit } }
  );
  return data;
};

export interface RecommendationItem {
  game: Game;
  score: number;
  reason: string[];
}

export interface RecommendationResponse {
  source_game: Game;
  model: string;
  recommendations: RecommendationItem[];
}

export const fetchRecommendations = async (
  bgg_id: number,
  model: string = 'hybrid',
  limit: number = 10
): Promise<RecommendationResponse> => {
  const { data } = await apiClient.get<RecommendationResponse>(
    `/api/games/${bgg_id}/recommendations`,
    { params: { model, limit } }
  );
  return data;
};

export interface RecommendationModel {
  id: string;
  paradigm: string;
  name: string;
  description: string;
}

export const fetchRecommendationModels = async (): Promise<RecommendationModel[]> => {
  const { data } = await apiClient.get<{ models: RecommendationModel[] }>('/api/recommendation-models');
  return data.models;
};

export const fetchReviews = async (
  bgg_id: number,
  page: number = 1,
  page_size: number = 10,
  min_rating?: number,
  max_rating?: number,
  language?: string
): Promise<PaginatedReviews> => {
  const { data } = await apiClient.get<PaginatedReviews>(
    `/api/games/${bgg_id}/reviews`,
    { params: { page, page_size, min_rating, max_rating, language } }
  );
  return data;
};
