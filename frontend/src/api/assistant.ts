import { useMutation } from '@tanstack/react-query';

export interface ParsedIntent {
  intent: string;
  query?: string;
  game_name?: string;
  game_names?: string[];
  filters?: any;
  needs_clarification?: boolean;
  clarification_question?: string;
}

export interface AssistantResponse {
  message: string;
  type: string; // 'search_results', 'recommendations', 'comparison', 'clarification', 'game_detail', 'error'
  parsed_intent: ParsedIntent;
  data: any;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const chatWithAssistant = async (request: ChatRequest): Promise<AssistantResponse> => {
  const response = await fetch(`${API_URL}/api/assistant/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error('Network response was not ok');
  }
  return response.json();
};

export const useChatMutation = () => {
  return useMutation({
    mutationFn: chatWithAssistant,
  });
};
