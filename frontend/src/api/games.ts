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

export const fetchGames = async (
  skip: number = 0, 
  limit: number = 24,
  sortBy: string = 'rank',
  order: string = 'asc'
): Promise<PaginatedGames> => {
  const { data } = await apiClient.get<PaginatedGames>('/api/games', {
    params: { skip, limit, sort_by: sortBy, order },
  });
  return data;
};

export const fetchGame = async (bgg_id: number): Promise<Game> => {
  const { data } = await apiClient.get<Game>(`/api/games/${bgg_id}`);
  return data;
};
