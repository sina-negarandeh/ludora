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
  categories: string[];
  mechanics: string[];
  designers: string[];
  publishers: string[];
  artists: string[];
}

export interface PaginatedGames {
  total: number;
  items: Game[];
}

export interface GameQuery {
  query?: string;
  categories?: string[];
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
