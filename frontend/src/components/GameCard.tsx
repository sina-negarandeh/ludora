import React, { useRef, useState, useEffect } from 'react';
import type { Game } from "../api/games";
import { StarIcon, ClockIcon, UserGroupIcon, AcademicCapIcon, TrophyIcon, UserIcon } from '@heroicons/react/24/solid';
import { Link } from 'react-router-dom';

interface GameCardProps {
  game: Game;
  matchPercentage?: number;
}

const SUBDOMAIN_MAP: Record<string, string> = {
  'CGS': 'Collectible Game System',
  'Childrens': "Children's",
};

const ScrollingTitle: React.FC<{ title: string; year: number }> = ({ title, year }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLHeadingElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);

  useEffect(() => {
    const checkOverflow = () => {
      if (containerRef.current && textRef.current) {
        setIsOverflowing(textRef.current.scrollWidth > containerRef.current.clientWidth);
      }
    };
    checkOverflow();
    window.addEventListener('resize', checkOverflow);
    return () => window.removeEventListener('resize', checkOverflow);
  }, [title]);

  return (
    <div 
      ref={containerRef}
      className="relative w-full overflow-hidden mb-2 [container-type:inline-size]"
      style={{ 
        maskImage: isOverflowing ? 'linear-gradient(to right, transparent 0%, black 5%, black 95%, transparent 100%)' : 'none',
        WebkitMaskImage: isOverflowing ? 'linear-gradient(to right, transparent 0%, black 5%, black 95%, transparent 100%)' : 'none'
      }}
    >
      <h3 
        ref={textRef}
        className={`text-2xl font-serif text-text leading-snug tracking-wide whitespace-nowrap w-max transition-transform duration-[4000ms] ease-in-out ${isOverflowing ? 'hover:translate-x-[calc(100cqw-100%)] cursor-ew-resize' : ''}`}
      >
        {title} <span className="text-secondary-text opacity-90 text-[1.3rem] tracking-normal">({year})</span>
      </h3>
    </div>
  );
};

const CircularProgress: React.FC<{ percentage: number }> = ({ percentage }) => {
  const radius = 16;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  
  return (
    <div className="relative flex items-center justify-center w-11 h-11 bg-white/90 backdrop-blur-md rounded-full shadow-sm border border-white/40 text-text">
      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 40 40">
        <circle
          className="text-neutral/30"
          strokeWidth="3.5"
          stroke="currentColor"
          fill="transparent"
          r={radius}
          cx="20"
          cy="20"
        />
        <circle
          className="text-primary transition-all duration-1000 ease-out"
          strokeWidth="3.5"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          stroke="currentColor"
          fill="transparent"
          r={radius}
          cx="20"
          cy="20"
        />
      </svg>
      <span className="absolute text-[10px] font-extrabold">{percentage}%</span>
    </div>
  );
};

export const GameCard: React.FC<GameCardProps> = ({ game, matchPercentage }) => {
  const renderComplexityDots = (weight: number | null | undefined) => {
    if (!weight) return <span className="text-secondary-text">N/A</span>;
    const dots = [];
    const rounded = Math.round(weight);
    for (let i = 1; i <= 5; i++) {
      dots.push(
        <span key={i} className={`w-1.5 h-1.5 rounded-full ${i <= rounded ? 'bg-primary' : 'bg-neutral/40'}`}></span>
      );
    }
    return (
      <div className="flex items-center gap-1.5" title={`Complexity: ${weight.toFixed(1)} / 5`}>
        <span className="text-secondary-text hidden sm:inline mr-1">{weight.toFixed(1)}</span>
        <div className="flex gap-0.5">{dots}</div>
      </div>
    );
  };

  return (
    <Link 
      to={`/games/${game.bgg_id}`}
      className="card flex flex-col group h-full cursor-pointer hover:-translate-y-1 transition-all duration-300"
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-surface group">
        {game.image_path ? (
          <>
            <img
              src={game.image_path}
              alt=""
              className="absolute inset-0 w-full h-full object-cover blur-xl opacity-40 scale-110"
              aria-hidden="true"
              loading="lazy"
            />
            <img
              src={game.image_path}
              alt={game.name}
              className="relative z-10 w-full h-full object-contain group-hover:scale-105 transition-transform duration-500 ease-in-out drop-shadow-lg"
              loading="lazy"
            />
          </>
        ) : (
          <div className="w-full h-full flex items-center justify-center text-secondary-text relative z-10">
            No Image
          </div>
        )}
        
        {matchPercentage !== undefined && (
          <div className="absolute top-3 right-3 z-20">
            <CircularProgress percentage={matchPercentage} />
          </div>
        )}
        
        <div className="absolute bottom-3 right-3 z-20 flex items-center gap-2 bg-white/85 backdrop-blur-md px-3 py-1 rounded-full shadow-sm border border-white/20 text-text">
          <div className="flex items-center gap-1">
            <StarIcon className="w-4 h-4 text-primary" />
            <span className="text-sm font-bold">{game.avg_rating ? game.avg_rating.toFixed(1) : 'N/A'}</span>
          </div>
          {game.rank && game.rank > 0 && (
            <>
              <div className="w-px h-3.5 bg-neutral/40"></div>
              <div className="flex items-center gap-1">
                <TrophyIcon className="w-4 h-4 text-primary" />
                <span className="text-sm font-bold">#{game.rank}</span>
              </div>
            </>
          )}
        </div>
      </div>
      
      <div className="p-4 flex flex-col flex-grow">
        <ScrollingTitle title={game.name} year={game.year_published} />
        
        <div className="flex flex-wrap items-center gap-1.5 h-[1.75rem] overflow-hidden mb-4">
          {game.subdomains && game.subdomains.map(sub => (
             <span key={sub} className="inline-flex items-center px-2 py-0.5 bg-surface text-secondary-text rounded text-[10px] font-bold uppercase tracking-wider border border-neutral/30 leading-none h-5">
               {SUBDOMAIN_MAP[sub] || sub}
             </span>
          ))}
        </div>
        
        <div className="mt-auto grid grid-cols-2 gap-y-3 gap-x-2 text-sm text-text border-t border-neutral/20 pt-4">
          <div className="flex items-center gap-1.5" title="Players">
            <UserGroupIcon className="w-4 h-4 text-neutral" />
            <span className="truncate">{game.min_players && game.min_players > 0 ? `${game.min_players}-${game.max_players} Players` : '—'}</span>
          </div>
          <div className="flex items-center gap-1.5" title="Playtime">
            <ClockIcon className="w-4 h-4 text-neutral" />
            <span className="truncate">{game.mfg_playtime && game.mfg_playtime > 0 ? `${game.mfg_playtime} min` : '—'}</span>
          </div>
          <div className="flex items-center gap-1.5" title="Complexity">
            <AcademicCapIcon className="w-4 h-4 text-neutral" />
            {renderComplexityDots(game.game_weight)}
          </div>
          <div className="flex items-center gap-1.5" title="Minimum Age">
             <UserIcon className="w-4 h-4 text-neutral" />
             <span className="truncate">{game.min_age && game.min_age > 0 ? `Age ${game.min_age}+` : '—'}</span>
          </div>
        </div>
      </div>
    </Link>
  );
};
