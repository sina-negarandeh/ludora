import React from 'react';
import type { AssistantData } from '../api/assistant';
import { CompactGameRow } from './CompactGameRow';

interface AssistantMessageBubbleProps {
  message: string;
  responseType?: string;
  data?: AssistantData;
  onSelectOption?: (option: string) => void;
}

export const AssistantMessageBubble: React.FC<AssistantMessageBubbleProps> = ({ message, responseType, data, onSelectOption }) => {
  return (
    <div className="flex flex-col gap-3 max-w-[90%] w-full self-start">
      <div className="bg-white/80 backdrop-blur-md border border-primary/20 px-4 py-3 rounded-2xl rounded-tl-sm text-text shadow-sm text-sm">
        {message}
      </div>

      {responseType === 'search_results' && data?.games && (
        <div className="flex flex-col gap-2">
          {data.games.slice(0, 5).map((game) => (
            <CompactGameRow key={game.bgg_id} game={game} />
          ))}
          {data.games.length > 5 && (
            <div className="text-xs text-secondary-text px-2 italic">+ {data.games.length - 5} more</div>
          )}
        </div>
      )}
      
      {responseType === 'search_results' && data?.results && (
        <div className="flex flex-col gap-2">
          {data.results.slice(0, 5).map((r) => (
            <CompactGameRow key={r.game.bgg_id} game={r.game} />
          ))}
        </div>
      )}

      {responseType === 'comparison' && data?.games && (
        <div className="flex overflow-x-auto gap-3 pb-2 w-[85vw] md:w-[350px]">
          {data.games.map((game) => (
            <div key={game.bgg_id} className="min-w-[200px] bg-white border border-neutral/20 rounded-xl p-3 flex flex-col gap-2 shadow-sm">
              <span className="font-bold text-sm truncate">{game.name}</span>
              <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
                <span className="text-secondary-text">Rating</span>
                <span className="font-bold text-right">{game.avg_rating?.toFixed(1)}</span>
                <span className="text-secondary-text">Weight</span>
                <span className="font-bold text-right">{game.game_weight?.toFixed(2)}</span>
                <span className="text-secondary-text">Players</span>
                <span className="text-right">{game.min_players}-{game.max_players}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {responseType === 'recommendations' && data?.recommendations && (
        <div className="flex flex-col gap-3">
          {data.recommendations.map((r) => (
            <div key={r.game.bgg_id} className="flex flex-col gap-1 bg-surface border border-primary/20 rounded-xl p-3">
              <CompactGameRow game={r.game} />
              {r.reason && r.reason.length > 0 && (
                <span className="text-[11px] text-secondary-text mt-1 px-1 line-clamp-2">
                  " {r.reason.join(" ")} "
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {responseType === 'clarification' && data?.ambiguous_matches && (
        <div className="flex flex-col gap-2 mt-1">
          {data.ambiguous_matches.map((match) => (
            <button
              key={match.id}
              onClick={() => onSelectOption && onSelectOption(match.name)}
              className="text-left text-sm bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 rounded-lg px-4 py-2 transition-colors"
            >
              {match.name} <span className="opacity-70 text-xs">({match.year})</span>
            </button>
          ))}
        </div>
      )}

      {responseType === 'game_detail' && data?.game && (
        <div className="w-full">
           <CompactGameRow game={data.game} />
        </div>
      )}
    </div>
  );
};
