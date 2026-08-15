import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import DOMPurify from 'dompurify';
import { fetchGame } from '../api/games';
import type { Game } from '../api/games';
import { StarIcon, ClockIcon, UserGroupIcon, AcademicCapIcon, TrophyIcon, UserIcon, ArrowLeftIcon } from '@heroicons/react/24/solid';

const CATEGORY_MAP: Record<string, string> = {
  'CGS': 'Collectible Game System',
  'Childrens': "Children's",
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
      <Link to="/games" className="inline-flex items-center gap-2 text-primary font-bold hover:text-primary-focus transition-colors mb-8 bg-surface px-5 py-2.5 rounded-full shadow-sm border border-neutral">
        <ArrowLeftIcon className="w-5 h-5" />
        Back to games
      </Link>

      {/* Hero Section */}
      <div className="relative w-full aspect-[16/9] md:aspect-[21/9] rounded-3xl overflow-hidden mb-12 shadow-lg bg-neutral/10 flex items-center justify-center group">
        {game.image_path && (
          <>
            {/* Ambient Background */}
            <div 
              className="absolute inset-0 bg-cover bg-center blur-3xl opacity-60 scale-110"
              style={{ backgroundImage: `url(${game.image_path})` }}
            />
            {/* Crisp Foreground Image */}
            <img 
              src={game.image_path} 
              alt={game.name}
              className="relative z-10 max-h-[90%] max-w-[90%] object-contain drop-shadow-2xl transition-transform duration-500 group-hover:scale-105"
            />
          </>
        )}
      </div>

      {/* Title & Core Metadata */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
        <div>
          <h1 className="text-5xl sm:text-7xl font-serif text-text leading-tight mb-2">
            {game.name}
          </h1>
          <p className="text-2xl text-secondary-text font-medium">
            Published {game.year_published}
          </p>
        </div>
        
        <div className="flex flex-wrap items-center gap-3">
          {game.categories && game.categories.split(',').map(cat => (
             <span key={cat} className="px-4 py-2 bg-neutral/20 text-text rounded-full text-sm font-bold whitespace-nowrap">
               {CATEGORY_MAP[cat.trim()] || cat.trim()}
             </span>
          ))}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-16">
        {game.rank && (
          <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
            <TrophyIcon className="w-8 h-8 text-yellow-500 mb-2" />
            <span className="text-sm text-secondary-text font-bold mb-1">Rank</span>
            <span className="text-2xl font-bold text-text">#{game.rank}</span>
          </div>
        )}
        <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
          <StarIcon className="w-8 h-8 text-yellow-400 mb-2" />
          <span className="text-sm text-secondary-text font-bold mb-1">Rating</span>
          <span className="text-2xl font-bold text-text">{game.avg_rating.toFixed(1)}</span>
        </div>
        <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
          <ClockIcon className="w-8 h-8 text-blue-500 mb-2" />
          <span className="text-sm text-secondary-text font-bold mb-1">Playtime</span>
          <span className="text-xl font-bold text-text">{game.mfg_playtime > 0 ? `${game.mfg_playtime} min` : '—'}</span>
        </div>
        <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
          <UserGroupIcon className="w-8 h-8 text-green-500 mb-2" />
          <span className="text-sm text-secondary-text font-bold mb-1">Players</span>
          <span className="text-xl font-bold text-text">
            {game.min_players === game.max_players ? game.min_players : `${game.min_players}-${game.max_players}`}
          </span>
        </div>
        <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
          <AcademicCapIcon className="w-8 h-8 text-purple-500 mb-2" />
          <span className="text-sm text-secondary-text font-bold mb-1">Complexity</span>
          <span className="text-xl font-bold text-text">{game.game_weight.toFixed(2)} / 5</span>
        </div>
        <div className="bg-surface border border-neutral rounded-2xl p-5 flex flex-col items-center justify-center text-center shadow-sm hover:-translate-y-1 transition-transform">
          <UserIcon className="w-8 h-8 text-orange-500 mb-2" />
          <span className="text-sm text-secondary-text font-bold mb-1">Min Age</span>
          <span className="text-xl font-bold text-text">{game.min_age > 0 ? `${game.min_age}+` : '—'}</span>
        </div>
      </div>

      {/* Description */}
      <div className="max-w-4xl">
        <h2 className="text-4xl font-serif text-text mb-6">About the Game</h2>
        <div 
          className="text-lg text-secondary-text leading-relaxed space-y-5"
          dangerouslySetInnerHTML={{ __html: cleanDescription }}
        />
      </div>
    </div>
  );
};
