import { useMutation } from '@tanstack/react-query';
import { AxiosError } from 'axios';

import { apiClient } from './games';
import type { Game, GameQuery } from './games';

export interface ClarificationMatch {
  id: number;
  name: string;
  year: number;
}

export interface EvidenceSample {
  sentiment: string;
  text: string;
}

export interface AspectAggregate {
  aspect: string;
  positive_count: number;
  negative_count: number;
  mixed_count: number;
  neutral_count: number;
  total_mentions: number;
  mean_sentiment: number;
  evidence_samples: EvidenceSample[];
}

export interface ReviewItem {
  id: number;
  user: string;
  rating: number | null;
  comment: string | null;
}

export interface AssistantData {
  games?: Game[];
  results?: { game: Game }[];
  recommendations?: { game: Game; score: number; reason: string[] }[];
  ambiguous_matches?: ClarificationMatch[];
  game?: Game;
  summary?: string | null;
  aspects?: AspectAggregate[];
  reviews?: ReviewItem[];
  total?: number;
}

export interface ParsedIntent {
  intent: string;
  query?: string;
  game_name?: string;
  game_names?: string[];
  filters?: GameQuery;
  needs_clarification?: boolean;
  clarification_question?: string;
}

export interface AssistantResponse {
  message: string;
  type: string; // 'search_results', 'recommendations', 'clarification', 'game_detail', 'community_consensus', 'reviews', 'comparison', 'error'
  parsed_intent: ParsedIntent;
  data?: AssistantData;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export const chatWithAssistant = async (request: ChatRequest): Promise<AssistantResponse> => {
  try {
    const { data } = await apiClient.post<AssistantResponse>('/api/assistant/chat', request);
    return data;
  } catch (err) {
    // Surface the backend's actual detail message (e.g. "The assistant
    // returned a response that couldn't be parsed...") instead of a
    // generic string -- the backend deliberately returns a safe, specific
    // message here (never a raw exception), so it's safe to show directly.
    if (err instanceof AxiosError && err.response?.data?.detail) {
      throw new Error(err.response.data.detail);
    }
    throw new Error('Could not reach the assistant. Please check your connection and try again.');
  }
};

export const useChatMutation = () => {
  return useMutation({
    mutationFn: chatWithAssistant,
  });
};
