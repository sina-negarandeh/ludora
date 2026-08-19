import React from 'react';
import { Link } from 'react-router-dom';
import type { AssistantData, AspectAggregate } from '../api/assistant';
import type { Game } from '../api/games';
import { CompactGameRow } from './CompactGameRow';
import { StarIcon, ExclamationTriangleIcon } from '@heroicons/react/24/solid';

interface AssistantMessageBubbleProps {
  message: string;
  responseType?: string;
  data?: AssistantData;
  onSelectOption?: (option: string) => void;
}

// Same Positive/Negative/Mixed dominance rule as the game page's aspect
// cards and the assistant backend's _describe_aspect (which uses
// ABSAConfig.CARD_DOMINANCE_THRESHOLD) -- kept as a literal here since
// there's no shared config the frontend can import from the Python
// backend; must stay in sync with that constant by hand.
const ASPECT_DOMINANCE_THRESHOLD = 0.6;

const AspectChip: React.FC<{ aspect: AspectAggregate }> = ({ aspect }) => {
  const total = Math.max(1, aspect.total_mentions);
  const posRatio = aspect.positive_count / total;
  const negRatio = aspect.negative_count / total;

  let label: string;
  let colorClasses: string;
  if (posRatio >= ASPECT_DOMINANCE_THRESHOLD) {
    label = `${Math.round(posRatio * 100)}% positive`;
    colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200';
  } else if (negRatio >= ASPECT_DOMINANCE_THRESHOLD) {
    label = `${Math.round(negRatio * 100)}% negative`;
    colorClasses = 'bg-red-50 text-red-700 border-red-200';
  } else {
    label = 'mixed';
    colorClasses = 'bg-neutral/10 text-secondary-text border-neutral/20';
  }

  const evidence = aspect.evidence_samples?.[0]?.text;

  return (
    <div className={`flex flex-col gap-1 rounded-xl border px-3 py-2 ${colorClasses}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-bold text-xs">{aspect.aspect}</span>
        <span className="text-[11px] font-bold shrink-0">{label}</span>
      </div>
      {evidence && (
        <span className="text-[11px] opacity-80 line-clamp-2">&ldquo;{evidence}&rdquo;</span>
      )}
    </div>
  );
};

const ReviewCard: React.FC<{ review: NonNullable<AssistantData['reviews']>[number] }> = ({ review }) => (
  <div className="flex flex-col gap-1 bg-white border border-neutral/20 rounded-xl p-3 shadow-sm">
    <div className="flex items-center justify-between">
      <span className="font-bold text-xs text-text">{review.user}</span>
      {review.rating !== null && (
        <span className="flex items-center gap-0.5 text-xs font-bold text-primary">
          <StarIcon className="w-3 h-3" /> {review.rating}/10
        </span>
      )}
    </div>
    {review.comment && (
      <p className="text-xs text-secondary-text leading-relaxed line-clamp-4">{review.comment}</p>
    )}
  </div>
);

// Same "Official" fields the game detail page's stat cards show (not the
// Community percentile/poll stats) -- one row per attribute, one column
// per compared game.
const COMPARISON_ROWS: { label: string; value: (g: Game) => string }[] = [
  { label: 'Rating', value: (g) => (g.avg_rating != null ? g.avg_rating.toFixed(1) : '—') },
  { label: 'Rank', value: (g) => (g.rank ? `#${g.rank}` : '—') },
  { label: 'Complexity', value: (g) => (g.game_weight != null ? `${g.game_weight.toFixed(2)}/5` : '—') },
  { label: 'Players', value: (g) => (g.min_players && g.max_players ? `${g.min_players}-${g.max_players}` : '—') },
  { label: 'Playtime', value: (g) => (g.mfg_playtime ? `${g.mfg_playtime}m` : '—') },
  { label: 'Min Age', value: (g) => (g.min_age ? `${g.min_age}+` : '—') },
];

const ComparisonTable: React.FC<{ games: Game[] }> = ({ games }) => (
  <div className="overflow-x-auto rounded-xl border border-neutral/20 bg-white shadow-sm">
    <table className="text-xs">
      <thead>
        <tr className="border-b border-neutral/20">
          <th className="sticky left-0 bg-white px-3 py-2" />
          {games.map((g) => (
            <th key={g.bgg_id} className="px-3 py-2 text-left align-bottom min-w-[110px]">
              <Link to={`/games/${g.bgg_id}`} className="font-bold text-text hover:text-primary line-clamp-2">
                {g.name}
              </Link>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {COMPARISON_ROWS.map((row) => (
          <tr key={row.label} className="border-b border-neutral/10 last:border-0">
            <td className="sticky left-0 bg-white px-3 py-2 font-bold text-secondary-text whitespace-nowrap">{row.label}</td>
            {games.map((g) => (
              <td key={g.bgg_id} className="px-3 py-2 text-text">{row.value(g)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export const AssistantMessageBubble: React.FC<AssistantMessageBubbleProps> = ({ message, responseType, data, onSelectOption }) => {
  const isError = responseType === 'error';

  return (
    <div className="flex flex-col gap-3 max-w-[90%] w-full self-start">
      <div className={`px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm text-sm flex items-start gap-2 ${
        isError
          ? 'bg-red-50/90 backdrop-blur-md border border-red-200 text-red-900'
          : 'bg-white/80 backdrop-blur-md border border-primary/20 text-text'
      }`}>
        {isError && <ExclamationTriangleIcon className="w-4 h-4 mt-0.5 shrink-0 text-red-500" />}
        <span>{message}</span>
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

      {responseType === 'community_consensus' && data?.game && (
        <div className="flex flex-col gap-2 w-full">
          <CompactGameRow game={data.game} />
          {data.aspects && data.aspects.length > 0 && (
            <div className="flex flex-col gap-1.5">
              {data.aspects.slice(0, 6).map((a) => (
                <AspectChip key={a.aspect} aspect={a} />
              ))}
              {data.aspects.length > 6 && (
                <div className="text-xs text-secondary-text px-2 italic">+ {data.aspects.length - 6} more aspects</div>
              )}
            </div>
          )}
        </div>
      )}

      {responseType === 'comparison' && data?.games && data.games.length > 0 && (
        <ComparisonTable games={data.games} />
      )}

      {responseType === 'reviews' && data?.reviews && (
        <div className="flex flex-col gap-2">
          {data.reviews.map((r) => (
            <ReviewCard key={r.id} review={r} />
          ))}
          {data.total !== undefined && data.total > data.reviews.length && (
            <div className="text-xs text-secondary-text px-2 italic">{data.total.toLocaleString()} reviews total</div>
          )}
        </div>
      )}
    </div>
  );
};
