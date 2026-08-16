import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_URL,
});

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
  min_age: number;
  image_path?: string;
  rank?: number;
  num_ratings?: number;
  rating_distribution?: number[];
  category_ranks?: Record<string, number>;
  categories: string[];
  themes: string[];
  mechanics: string[];
  designers: string[];
  publishers: string[];
  artists: string[];
}

export interface Review {
  id: number;
  user: string;
  rating?: number;
  comment?: string;
  created_at?: string;
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
  categories?: string[];
  themes?: string[];
  mechanics?: string[];
  exact_players?: number;
  min_players?: number;
  max_players?: number;
  min_weight?: number;
  max_weight?: number;
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
  const { data } = await apiClient.get<string[]>('/api/games/categories');
  return data;
};

export interface ThemeMetadata {
  id: number;
  name: string;
  game_count: number;
}

export const fetchThemes = async (): Promise<ThemeMetadata[]> => {
  const { data } = await apiClient.get<ThemeMetadata[]>('/api/games/themes');
  return data;
};

export const fetchMechanics = async (): Promise<string[]> => {
  const { data } = await apiClient.get<string[]>('/api/games/mechanics');
  return data;
};

export const fetchDesigners = async (): Promise<string[]> => {
  const { data } = await apiClient.get<string[]>('/api/games/designers');
  return data;
};

export const fetchPublishers = async (): Promise<string[]> => {
  const { data } = await apiClient.get<string[]>('/api/games/publishers');
  return data;
};

export interface SearchQueryPayload {
  q: string;
  mode: 'lexical' | 'semantic' | 'hybrid';
  filters?: {
    categories?: string[];
    themes?: string[];
    mechanics?: string[];
    exact_players?: number;
    min_players?: number;
    max_players?: number;
    min_weight?: number;
    max_weight?: number;
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
