import React from 'react';
import type { Game } from '../api/games';
import { Link } from 'react-router-dom';
import { StarIcon, TrophyIcon } from '@heroicons/react/24/solid';

interface CompactGameRowProps {
  game: Game;
}

export const CompactGameRow: React.FC<CompactGameRowProps> = ({ game }) => (
  <Link to={`/games/${game.bgg_id}`} className="flex items-center gap-3 p-2 bg-white hover:bg-stone-50 border border-stone-200/60 shadow-sm rounded-lg transition-colors group">
    <div className="w-12 h-12 rounded overflow-hidden flex-shrink-0 bg-neutral/10">
      {game.image_path ? (
        <img src={game.image_path} alt={game.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-xs text-secondary-text">No img</div>
      )}
    </div>
    <div className="flex flex-col overflow-hidden">
      <span className="font-bold text-sm text-text truncate">{game.name} <span className="text-secondary-text font-normal text-xs">({game.year_published})</span></span>
      <span className="text-xs text-secondary-text truncate flex items-center gap-1.5 mt-0.5">
        <span className="flex items-center gap-0.5 font-bold text-primary"><StarIcon className="w-3 h-3" /> {game.avg_rating?.toFixed(1) || '-'}</span>
        {game.rank > 0 && <span className="flex items-center gap-0.5 font-bold text-yellow-600"><TrophyIcon className="w-3 h-3" /> {game.rank}</span>}
        <span className="text-neutral/30 mx-0.5">|</span>
        {game.min_players && <span>{game.min_players}-{game.max_players}p</span>}
        {game.game_weight > 0 && <span>• {game.game_weight.toFixed(2)}/5</span>}
        {game.mfg_playtime > 0 && <span>• {game.mfg_playtime}m</span>}
        {game.min_age > 0 && <span>• {game.min_age}+</span>}
      </span>
    </div>
  </Link>
);
