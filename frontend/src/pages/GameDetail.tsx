import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import DOMPurify from 'dompurify';
import { useQuery } from '@tanstack/react-query';
import { fetchGame, fetchRecommendations } from '../api/games';
import type { Game } from '../api/games';
import { GameCard } from '../components/GameCard';
import { StarIcon, ClockIcon, UserGroupIcon, AcademicCapIcon, TrophyIcon, UserIcon, ArrowLeftIcon } from '@heroicons/react/24/solid';

const CATEGORY_MAP: Record<string, string> = {
  'CGS': 'Collectible Game System',
  'Childrens': "Children's",
};

const ExpandableList: React.FC<{ items: string[], limit?: number }> = ({ items, limit = 3 }) => {
  const [expanded, setExpanded] = useState(false);
  const visibleItems = expanded ? items : items.slice(0, limit);
  const hiddenCount = items.length - limit;

  return (
    <div className="flex flex-col gap-2">
      {visibleItems.map(item => (
        <span key={item} className="text-secondary-text font-medium leading-snug">
          {item}
        </span>
      ))}
      {hiddenCount > 0 && (
        <button 
          onClick={() => setExpanded(!expanded)} 
          className="text-primary font-bold text-sm text-left hover:underline mt-1 w-fit transition-colors"
        >
          {expanded ? 'Show less' : `+ ${hiddenCount} more...`}
        </button>
      )}
    </div>
  );
};

const ExpandableChipList: React.FC<{ items: string[], limit?: number }> = ({ items, limit = 5 }) => {
  const [expanded, setExpanded] = useState(false);
  const visibleItems = expanded ? items : items.slice(0, limit);
  const hiddenCount = items.length - limit;

  return (
    <div className="flex flex-wrap gap-2">
      {visibleItems.map(item => (
        <span key={item} className="px-3 py-1.5 bg-surface border border-neutral rounded-lg text-sm text-secondary-text font-medium">
          {item}
        </span>
      ))}
      {hiddenCount > 0 && (
        <button 
          onClick={() => setExpanded(!expanded)} 
          className="px-3 py-1.5 text-primary text-sm font-bold hover:bg-neutral/10 rounded-lg transition-colors"
        >
          {expanded ? 'Show less' : `+ ${hiddenCount} more...`}
        </button>
      )}
    </div>
  );
};

const GameRecommendations: React.FC<{ bgg_id: number }> = ({ bgg_id }) => {
  const [model, setModel] = useState('hybrid');
  
  const { data, isLoading } = useQuery({
    queryKey: ['recommendations', bgg_id, model],
    queryFn: () => fetchRecommendations(bgg_id, model, 10),
  });

  return (
    <div className="mt-24 border-t border-neutral/20 pt-16">
      <div className="flex flex-col md:flex-row items-center justify-between mb-8 gap-4">
        <div>
          <h2 className="text-4xl font-serif text-text mb-2">Similar Games</h2>
          <p className="text-secondary-text">Matches based on shared items characteristics.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <label htmlFor="model-select" className="text-sm font-bold text-secondary-text uppercase tracking-wider">
            Algorithm
          </label>
          <select
            id="model-select"
            value={model}
            onChange={e => setModel(e.target.value)}
            className="bg-surface border border-neutral text-text font-medium rounded-xl px-4 py-2 focus:ring-2 focus:ring-primary outline-none cursor-pointer shadow-sm"
          >
            <option value="popularity">Popularity Baseline</option>
            <option value="metadata">Content-Based: Metadata</option>
            <option value="tfidf">NLP-Based: TF-IDF</option>
            <option value="embedding">Semantic: Embedding</option>
            <option value="hybrid">Hybrid Ranking</option>
            <option value="graph_jaccard">Graph: Weighted Jaccard</option>
            <option value="node2vec">Graph: DeepWalk (Node2Vec)</option>
          </select>
        </div>
      </div>
      
      {isLoading ? (
        <div className="flex gap-6 overflow-x-auto pb-8 snap-x">
           {[1,2,3,4,5].map(i => <div key={i} className="min-w-[240px] h-[320px] bg-neutral/10 rounded-2xl animate-pulse snap-start" />)}
        </div>
      ) : data?.recommendations?.length === 0 ? (
        <div className="text-center py-12 text-secondary-text">No recommendations found.</div>
      ) : (
        <div className="flex gap-6 overflow-x-auto pb-8 snap-x" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
          {data?.recommendations.map(rec => (
            <div key={rec.game.bgg_id || rec.game.id} className="min-w-[300px] max-w-[300px] snap-start flex flex-col gap-3">
              <div className="flex-1">
                <GameCard 
                  game={rec.game as any} 
                  matchPercentage={model === 'popularity' ? undefined : Math.round(rec.score * 100)} 
                />
              </div>
              {rec.reason && rec.reason.length > 0 && (
                <div className="text-xs font-medium text-primary bg-primary/10 border border-primary/20 px-3 py-2 rounded-lg line-clamp-2 leading-relaxed shrink-0 shadow-sm">
                  {rec.reason[0]}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const GameDetail: React.FC = () => {
  const { bgg_id } = useParams<{ bgg_id: string }>();
  const [game, setGame] = useState<Game | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadGame = async () => {
      try {
        setIsLoading(true);
        setError(null);
        if (!bgg_id) return;
        const data = await fetchGame(parseInt(bgg_id));
        setGame(data);
      } catch (err: any) {
        if (err.response?.status === 404) {
          setError('404');
        } else {
          setError('Something went wrong loading this game.');
        }
      } finally {
        setIsLoading(false);
      }
    };
    
    // Scroll to top when loading new game
    window.scrollTo(0, 0);
    loadGame();
  }, [bgg_id]);

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8 animate-pulse">
        <div className="h-10 w-32 bg-neutral/20 rounded-full mb-8"></div>
        <div className="w-full aspect-[21/9] bg-neutral/20 rounded-3xl mb-12"></div>
        <div className="h-16 w-3/4 bg-neutral/20 rounded-xl mb-6"></div>
        <div className="h-8 w-1/4 bg-neutral/20 rounded-lg mb-12"></div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-16">
           {[1,2,3,4,5,6].map(i => <div key={i} className="h-32 bg-neutral/20 rounded-2xl"></div>)}
        </div>
        <div className="space-y-4 max-w-4xl">
          <div className="h-4 bg-neutral/20 rounded w-full"></div>
          <div className="h-4 bg-neutral/20 rounded w-5/6"></div>
          <div className="h-4 bg-neutral/20 rounded w-4/6"></div>
          <div className="h-4 bg-neutral/20 rounded w-full"></div>
          <div className="h-4 bg-neutral/20 rounded w-3/4"></div>
        </div>
      </div>
    );
  }

  if (error === '404' || (!game && !isLoading)) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4">
        <h2 className="text-4xl font-serif text-text mb-4">Game not found</h2>
        <p className="text-secondary-text mb-8">The requested board game doesn't exist.</p>
        <Link to="/games" className="bg-primary text-white font-bold py-3 px-6 rounded-xl hover:bg-primary-focus transition-colors flex items-center gap-2">
          <ArrowLeftIcon className="w-5 h-5" /> Back to games
        </Link>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4">
        <h2 className="text-3xl font-serif text-text mb-4">API Failure</h2>
        <p className="text-secondary-text mb-8">{error}</p>
        <button onClick={() => window.location.reload()} className="bg-primary text-white font-bold py-3 px-6 rounded-xl hover:bg-primary-focus transition-colors">
          Try again
        </button>
      </div>
    );
  }

  if (!game) return null;

  // Sanitize HTML description safely
  const cleanDescription = DOMPurify.sanitize(game.description || 'No description available.');

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Fixed Back Button */}
      <div className="fixed top-24 left-4 z-40 pointer-events-none">
        <Link to="/games" className="pointer-events-auto bg-white/80 backdrop-blur-md px-6 shadow-sm border border-neutral/20 flex items-center gap-2 h-[4rem] rounded-full text-primary font-bold hover:opacity-80 transition-opacity">
          <ArrowLeftIcon className="w-5 h-5" />
          <span>Back to games</span>
        </Link>
      </div>

      {/* Top Section: Box Art & Title */}
      <div className="flex flex-col md:flex-row gap-8 lg:gap-12 mb-16">
        {/* Left Column: Box Art */}
        <div className="w-full md:w-1/3 lg:w-1/4 shrink-0 flex justify-center md:justify-start">
          {game.image_path ? (
            <div className="relative group w-full max-w-[320px] md:max-w-none">
              {/* Ambient Glow */}
              <div 
                className="absolute inset-0 bg-cover bg-center blur-2xl opacity-40 scale-105 translate-y-4"
                style={{ backgroundImage: `url(${game.image_path})` }}
              />
              <img 
                src={game.image_path} 
                alt={game.name}
                className="relative z-10 w-full h-auto object-contain rounded-2xl shadow-2xl transition-transform duration-500 group-hover:scale-[1.02]"
              />
            </div>
          ) : (
            <div className="w-full max-w-[320px] md:max-w-none aspect-[3/4] bg-neutral/10 rounded-2xl flex items-center justify-center">
              <span className="text-secondary-text">No image available</span>
            </div>
          )}
        </div>

        {/* Right Column: Title & Metadata */}
        <div className="flex-1 flex flex-col justify-center py-4">
          <h1 className="text-5xl sm:text-7xl font-serif text-text leading-tight mb-4">
            {game.name}
          </h1>
          <p className="text-2xl text-secondary-text font-medium mb-6">
            Published {game.year_published}
          </p>

          <div className="flex flex-wrap items-center gap-3">
            {game.categories && game.categories.map(cat => (
               <span key={cat} className="px-4 py-2 bg-neutral/20 text-text rounded-full text-sm font-bold whitespace-nowrap">
                 {CATEGORY_MAP[cat] || cat}
               </span>
            ))}
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-16">
        {game.rank && (
          <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
            <TrophyIcon className="w-8 h-8 text-primary mb-2 opacity-80" />
            <span className="text-sm text-secondary-text font-bold mb-1">Rank</span>
            <span className="text-2xl font-bold text-text">#{game.rank}</span>
          </div>
        )}
        <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
          <StarIcon className="w-8 h-8 text-primary mb-2 opacity-80" />
          <span className="text-sm text-secondary-text font-bold mb-1">Rating</span>
          <span className="text-xl font-bold text-text">{game.avg_rating.toFixed(1)} / 10</span>
        </div>
        <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
          <ClockIcon className="w-8 h-8 text-primary mb-2 opacity-80" />
          <span className="text-sm text-secondary-text font-bold mb-1">Playtime</span>
          <span className="text-xl font-bold text-text">{game.mfg_playtime > 0 ? `${game.mfg_playtime} min` : '—'}</span>
        </div>
        <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
          <UserGroupIcon className="w-8 h-8 text-primary mb-2 opacity-80" />
          <span className="text-sm text-secondary-text font-bold mb-1">Players</span>
          <span className="text-xl font-bold text-text">
            {game.min_players === game.max_players ? game.min_players : `${game.min_players}-${game.max_players}`}
          </span>
        </div>
        <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
          <AcademicCapIcon className="w-8 h-8 text-primary mb-2 opacity-80" />
          <span className="text-sm text-secondary-text font-bold mb-1">Complexity</span>
          <span className="text-xl font-bold text-text">{game.game_weight.toFixed(2)} / 5</span>
        </div>
        <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
          <UserIcon className="w-8 h-8 text-primary mb-2 opacity-80" />
          <span className="text-sm text-secondary-text font-bold mb-1">Min Age</span>
          <span className="text-xl font-bold text-text">{game.min_age > 0 ? `${game.min_age}+` : '—'}</span>
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
        {/* Description */}
        <div className="lg:col-span-2">
          <h2 className="text-4xl font-serif text-text mb-6">About the Game</h2>
          <div 
            className="text-lg text-secondary-text leading-relaxed space-y-5"
            dangerouslySetInnerHTML={{ __html: cleanDescription }}
          />
        </div>

        {/* Sidebar Entities */}
        <div className="space-y-10">
          {game.mechanics && game.mechanics.length > 0 && (
            <div>
              <h3 className="text-2xl font-serif text-text mb-4">Mechanics</h3>
              <ExpandableChipList items={game.mechanics} limit={6} />
            </div>
          )}

          {game.designers && game.designers.length > 0 && (
            <div>
              <h3 className="text-2xl font-serif text-text mb-4">Designers</h3>
              <ExpandableList items={game.designers} limit={3} />
            </div>
          )}

          {game.artists && game.artists.length > 0 && (
            <div>
              <h3 className="text-2xl font-serif text-text mb-4">Artists</h3>
              <ExpandableList items={game.artists} limit={3} />
            </div>
          )}

          {game.publishers && game.publishers.length > 0 && (
            <div>
              <h3 className="text-2xl font-serif text-text mb-4">Publishers</h3>
              <ExpandableList items={game.publishers} limit={3} />
            </div>
          )}
        </div>
      </div>

      {/* Recommendations */}
      <GameRecommendations bgg_id={game.bgg_id} />
    </div>
  );
};
