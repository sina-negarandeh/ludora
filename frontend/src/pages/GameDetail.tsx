import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import DOMPurify from 'dompurify';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import axios from 'axios';
import { fetchGame, fetchRecommendations, fetchReviews } from '../api/games';
import type { Game } from '../api/games';
import { GameCard } from '../components/GameCard';
import { StarIcon, ClockIcon, UserGroupIcon, AcademicCapIcon, TrophyIcon, UserIcon, ArrowLeftIcon, HandThumbUpIcon, HandThumbDownIcon, SparklesIcon, ChatBubbleLeftRightIcon, CheckCircleIcon, XCircleIcon, MinusCircleIcon, QuestionMarkCircleIcon, LanguageIcon } from '@heroicons/react/24/solid';

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

const MODELS = [
  { id: 'popularity', name: 'Popularity Baseline', coverage: null, ild: null, category: 'Popularity-Based' },
  { id: 'metadata', name: 'Metadata Similarity', coverage: 96.13, ild: 0.52, category: 'Content-Based Filtering' },
  { id: 'tfidf', name: 'TF-IDF Vectorization', coverage: 95.41, ild: 0.44, category: 'Content-Based Filtering' },
  { id: 'embedding', name: 'Semantic Embedding', coverage: 93.54, ild: 0.34, category: 'Content-Based Filtering' },
  { id: 'hybrid', name: 'Hybrid System', coverage: 90.49, ild: 0.39, category: 'Content-Based Filtering' },
  { id: 'graph_jaccard', name: 'Graph Jaccard', coverage: 94.03, ild: 0.52, category: 'Content-Based Filtering' },
  { id: 'node2vec', name: 'Graph DeepWalk', coverage: 96.55, ild: 0.54, category: 'Content-Based Filtering' },
  { id: 'cf_item_cosine', name: 'Item-Item Cosine', coverage: null, ild: null, category: 'Collaborative Filtering' },
  { id: 'cf_svd', name: 'Matrix Factorization (SVD)', coverage: null, ild: null, category: 'Collaborative Filtering' },
  { id: 'cf_als', name: 'Alternating Least Squares (ALS)', coverage: null, ild: null, category: 'Collaborative Filtering' },
];

const RECSYS_TYPES = [
  { id: 'Popularity-Based', name: 'Popularity-Based', available: true },
  { id: 'Content-Based Filtering', name: 'Content-Based Filtering', available: true },
  { id: 'Collaborative Filtering', name: 'Collaborative Filtering', available: true },
  { id: 'Hybrid', name: 'Hybrid', available: false },
];

const GameRankings: React.FC<{ game: Game }> = ({ game }) => {
  const hasOverallRank = game.rank && game.rank > 0;
  const hasCategoryRanks = game.category_ranks && Object.keys(game.category_ranks).length > 0;
  
  if (!hasOverallRank && !hasCategoryRanks) return null;

  return (
    <div className="mt-24 border-t border-neutral/20 pt-16">
      <h2 className="text-4xl font-serif text-text mb-8">Rankings</h2>
      <div className="flex flex-wrap gap-4">
        {hasOverallRank && (
          <div className="flex items-center gap-3 bg-surface border border-primary/30 px-6 py-4 rounded-full shadow-sm hover:border-primary/60 transition-colors">
            <TrophyIcon className="w-6 h-6 text-primary" />
            <span className="font-bold text-text text-xl">#{game.rank}</span>
            <span className="text-secondary-text font-medium text-lg">Overall</span>
          </div>
        )}
        
        {hasCategoryRanks && Object.entries(game.category_ranks!).sort((a, b) => a[1] - b[1]).map(([category, rank]) => (
          <div key={category} className="flex items-center gap-3 bg-surface border border-neutral/30 px-6 py-4 rounded-full shadow-sm hover:border-neutral/60 transition-colors">
            <span className="font-bold text-text text-xl">#{rank}</span>
            <span className="text-secondary-text font-medium text-lg">{category}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// Distribution Interfaces
interface MetricDistribution {
  x: number[];
  density: number[];
  cdf: number[];
  min: number;
  max: number;
}
type CategoryDistributions = Record<string, MetricDistribution>;
type AllDistributions = Record<string, CategoryDistributions>;

const DistributionChart = ({ 
  title, 
  value, 
  metric, 
  category, 
  distributions,
  leftLabel,
  rightLabel,
  formatValue,
  formatPercentile,
  formatAvg
}: { 
  title: string, value: number, metric: string, category: string, distributions: AllDistributions,
  leftLabel: string, rightLabel: string, formatValue: (v: number) => string, formatPercentile: (cdf: number, catName: string) => string, formatAvg: (v: number) => string
}) => {
  const dist = distributions[category]?.[metric] || distributions['Overall']?.[metric];
  if (!dist) return null;

  const usedCategoryName = distributions[category]?.[metric] ? category : 'Overall';
  const displayCategory = usedCategoryName === 'Overall' ? 'All Games' : `${usedCategoryName} Games`;

  // Calculate Marker Position
  const p = Math.max(0, Math.min(1, (value - dist.min) / (dist.max - dist.min)));
  
  // Find CDF
  let closestIdx = 0;
  let minDiff = Infinity;
  for (let i = 0; i < dist.x.length; i++) {
    const diff = Math.abs(dist.x[i] - value);
    if (diff < minDiff) {
      minDiff = diff;
      closestIdx = i;
    }
  }
  const cdfValue = dist.cdf[closestIdx];

  // Expected value (average) from density
  const sumDensity = dist.density.reduce((a, b) => a + b, 0);
  const avgValue = sumDensity > 0 ? dist.density.reduce((sum, d, i) => sum + (dist.x[i] * d), 0) / sumDensity : 0;
  const avgP = Math.max(0, Math.min(1, (avgValue - dist.min) / (dist.max - dist.min)));

  // Smooth Path Generator
  const generateSmoothPath = (points: [number, number][]) => {
    if (points.length === 0) return '';
    if (points.length === 1) return `M ${points[0][0]},${points[0][1]}`;
    
    const controlPoint = (current: [number, number], previous: [number, number] | undefined, next: [number, number] | undefined, reverse: boolean) => {
      const p = previous || current;
      const n = next || current;
      const smoothing = 0.15;
      const lengthX = n[0] - p[0];
      const lengthY = n[1] - p[1];
      const length = Math.sqrt(Math.pow(lengthX, 2) + Math.pow(lengthY, 2)) * smoothing;
      const angle = Math.atan2(lengthY, lengthX) + (reverse ? Math.PI : 0);
      return [current[0] + Math.cos(angle) * length, current[1] + Math.sin(angle) * length];
    };

    let path = `M ${points[0][0]},${points[0][1]}`;
    for (let i = 1; i < points.length; i++) {
      const cps = controlPoint(points[i - 1], points[i - 2], points[i], false);
      const cpe = controlPoint(points[i], points[i - 1], points[i + 1], true);
      path += ` C ${cps[0]},${cps[1]} ${cpe[0]},${cpe[1]} ${points[i][0]},${points[i][1]}`;
    }
    return path;
  };

  // Find exact Y position on the curve for the marker
  let densityAtValue = 0;
  for (let i = 0; i < dist.x.length - 1; i++) {
    if (value >= dist.x[i] && value <= dist.x[i+1]) {
      const range = dist.x[i+1] - dist.x[i];
      const fraction = (value - dist.x[i]) / range;
      densityAtValue = dist.density[i] + fraction * (dist.density[i+1] - dist.density[i]);
      break;
    }
  }
  if (value <= dist.x[0]) densityAtValue = dist.density[0];
  if (value >= dist.x[dist.x.length-1]) densityAtValue = dist.density[dist.density.length-1];
  const markerY = 100 - (densityAtValue * 90);

  // SVG Path
  const pts: [number, number][] = dist.density.map((d, i) => {
    const x = (i / (dist.density.length - 1)) * 100;
    const y = 100 - (d * 90); // keep a 10% top margin
    return [x, y];
  });
  
  const pathLine = generateSmoothPath(pts);
  const pathD = `${pathLine} L 100,100 L 0,100 Z`;

  return (
    <div className="flex flex-col mb-8">
      <div className="flex justify-between items-baseline mb-2">
        <h4 className="text-lg font-bold text-text">{title}</h4>
        <span className="text-xl font-bold text-primary">{formatValue(value)}</span>
      </div>
      
      <div className="relative h-24 w-full mb-1 border-b-2 border-stone-300">
        {/* Background Area */}
        <svg className="w-full h-full overflow-visible absolute inset-0" preserveAspectRatio="none" viewBox="0 0 100 100">
          <path d={pathD} className="fill-primary/20" />
          <path d={pathLine} fill="none" className="stroke-primary/60 stroke-2" />
        </svg>

        {/* Average Marker */}
        <div 
          className="absolute top-0 bottom-0 flex flex-col items-center z-20 pointer-events-none"
          style={{ left: `${avgP * 100}%`, transform: 'translateX(-50%)' }}
        >
          <div className="absolute bg-surface/80 backdrop-blur-sm px-1 text-secondary-text/80 text-[9px] font-bold uppercase tracking-wider whitespace-nowrap leading-none py-0.5 bottom-full">
            AVG {formatAvg(avgValue)}
          </div>
          <div className="w-px border-l-2 border-dashed border-neutral/30 h-full relative" />
        </div>

        {/* This Game Marker */}
        <div 
          className="absolute top-0 bottom-0 flex flex-col items-center z-10 pointer-events-none"
          style={{ left: `${p * 100}%`, transform: 'translateX(-50%)' }}
        >
          <div className="text-primary text-[10px] font-bold whitespace-nowrap absolute leading-none pb-1" style={{ bottom: 'calc(100% + 14px)' }}>
            This Game
          </div>
          <div className="w-[2px] bg-primary absolute bottom-full" style={{ height: '14px' }} />
          <div className="w-[2px] bg-primary h-full relative">
            <div 
              className="absolute left-1/2 -translate-x-1/2 w-3 h-3 bg-primary rounded-full border-2 border-surface" 
              style={{ top: `${markerY}%`, marginTop: '-6px' }} 
            />
          </div>
        </div>
      </div>
      
      <div className="flex justify-between text-xs text-secondary-text/60 font-bold uppercase tracking-wider mb-2">
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>
      
      <p className="text-sm text-secondary-text font-medium">
        {formatPercentile(cdfValue, displayCategory)}
      </p>
    </div>
  );
};

const GameDistributions: React.FC<{ game: Game }> = ({ game }) => {
  const [distributions, setDistributions] = useState<AllDistributions | null>(null);

  useEffect(() => {
    fetch('/distributions.json')
      .then(r => r.json())
      .then(data => setDistributions(data))
      .catch(console.error);
  }, []);

  if (!distributions) return null;

  // Find primary category
  let primaryCategory = 'Overall';
  if (game.category_ranks && Object.keys(game.category_ranks).length > 0) {
    primaryCategory = Object.entries(game.category_ranks).sort((a, b) => a[1] - b[1])[0][0];
  }

  return (
    <div className="mt-24 border-t border-neutral/20 pt-16">
      <h2 className="text-4xl font-serif text-text mb-8">Stats</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-12">
        {game.game_weight != null && game.game_weight > 0 && (
          <DistributionChart 
            title="Complexity"
            value={game.game_weight}
            metric="Complexity"
            category={primaryCategory}
            distributions={distributions}
            leftLabel="Lighter"
            rightLabel="Heavier"
            formatValue={v => `${v.toFixed(2)} / 5`}
            formatAvg={v => v.toFixed(2)}
            formatPercentile={(cdf, cat) => `Heavier than ${Math.round(cdf * 100)}% of ${cat}`}
          />
        )}
        {game.mfg_playtime != null && game.mfg_playtime > 0 && (
          <DistributionChart 
            title="Playtime"
            value={game.mfg_playtime}
            metric="Playtime"
            category={primaryCategory}
            distributions={distributions}
            leftLabel="Shorter"
            rightLabel="Longer"
            formatValue={v => `${v} Mins`}
            formatAvg={v => Math.round(v).toString()}
            formatPercentile={(cdf, cat) => `Longer than ${Math.round(cdf * 100)}% of ${cat}`}
          />
        )}
        {game.min_age != null && game.min_age > 0 && (
          <DistributionChart 
            title="Minimum Age"
            value={game.min_age}
            metric="Min Age"
            category={primaryCategory}
            distributions={distributions}
            leftLabel="Younger"
            rightLabel="Older"
            formatValue={v => `${v}+ Years`}
            formatAvg={v => v.toFixed(1)}
            formatPercentile={(cdf, cat) => `More mature than ${Math.round(cdf * 100)}% of ${cat}`}
          />
        )}
        {game.max_players != null && game.max_players > 0 && (
          <DistributionChart 
            title="Max Players"
            value={game.max_players}
            metric="Players"
            category={primaryCategory}
            distributions={distributions}
            leftLabel="Fewer"
            rightLabel="More"
            formatValue={v => `${v} Players`}
            formatAvg={v => v.toFixed(1)}
            formatPercentile={(cdf, cat) => `Accommodates more players than ${Math.round(cdf * 100)}% of ${cat}`}
          />
        )}
      </div>
    </div>
  );
};

const UserRatings: React.FC<{ game: Game }> = ({ game }) => {
  if (!game.rating_distribution || !game.num_ratings || game.rating_distribution.length === 0) return null;

  // We now have 19 items in rating_distribution representing 1.0, 1.5, 2.0... 10.0
  // Group into 10 visual bins: 
  // Bin 0 (Bar 1): index 0 (1.0), index 1 (1.5)
  // ...
  // Bin 9 (Bar 10): index 18 (10.0)
  const groupedDistribution = Array.from({ length: 10 }, (_, i) => {
    const baseIndex = i * 2;
    const countWhole = game.rating_distribution![baseIndex] || 0;
    const countHalf = game.rating_distribution![baseIndex + 1] || 0;
    return {
      barNumber: i + 1,
      totalCount: countWhole + countHalf,
      countWhole,
      countHalf,
    };
  });

  const maxCount = Math.max(...groupedDistribution.map(b => b.totalCount));

  // Calculate "Recommended" percentage (scores 7.0+ -> indexes 12-18)
  const recommendedCount = game.rating_distribution.slice(12).reduce((sum, count) => sum + count, 0);
  const recommendedPercentage = game.num_ratings > 0 ? Math.round((recommendedCount / game.num_ratings) * 100) : 0;
  
  // Gauge chart math (75% arc)
  const gaugeRadius = 46;
  const gaugeCircumference = 2 * Math.PI * gaugeRadius;
  const gaugeArcLength = 0.75 * gaugeCircumference;
  const progressLength = (recommendedPercentage / 100) * gaugeArcLength;

  return (
    <div className="mt-24 border-t border-neutral/20 pt-16">
      <h2 className="text-4xl font-serif text-text mb-8">Ratings</h2>
      
      <div className="flex flex-col md:flex-row gap-16 items-start">
        {/* Left: Bar Plot */}
        <div className="flex-1 w-full flex flex-col relative">
          
          {/* Chart Area */}
          <div className="flex-1 w-full flex items-end gap-2 relative z-10 h-64">
            {/* Background Grid Lines */}
            <div className="absolute inset-0 flex flex-col justify-between pointer-events-none z-0">
              {[0, 1, 2, 3, 4].map((line) => (
                <div key={line} className={`w-full border-t ${line === 4 ? 'border-solid border-neutral/40' : 'border-dashed border-neutral/20'}`} />
              ))}
            </div>

            {/* Bars */}
            {groupedDistribution.map((bin, i) => {
              const heightPercentage = maxCount > 0 ? (bin.totalCount / maxCount) * 100 : 0;
              return (
                <div key={i} className="flex-1 flex flex-col items-center group h-full z-10">
                  <div className="w-full relative flex-1 flex items-end justify-center">
                    <div 
                      className="w-full bg-primary/60 group-hover:bg-primary transition-all duration-300 rounded-t-lg relative min-h-[4px]"
                      style={{ height: `${heightPercentage}%` }}
                    >
                      {/* Tooltip on hover */}
                      <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-surface shadow-md rounded-md px-3 py-2 text-xs text-text border border-neutral/20 pointer-events-none whitespace-nowrap z-20 flex flex-col items-center">
                        <span className="font-bold border-b border-neutral/20 pb-1 mb-1 w-full text-center">
                          Score {bin.barNumber}{bin.barNumber < 10 ? ` - ${bin.barNumber}.5` : '.0'}
                        </span>
                        <div className="flex flex-col gap-0.5 text-secondary-text w-full">
                          <div className="flex justify-between gap-4">
                            <span>{bin.barNumber}.0:</span>
                            <span className="font-medium text-text">{bin.countWhole.toLocaleString()}</span>
                          </div>
                          {bin.barNumber < 10 && (
                            <div className="flex justify-between gap-4">
                              <span>{bin.barNumber}.5:</span>
                              <span className="font-medium text-text">{bin.countHalf.toLocaleString()}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* X-Axis Labels */}
          <div className="flex items-center gap-2 mt-2 w-full z-10">
            {groupedDistribution.map((bin, i) => (
              <span key={i} className="flex-1 text-center text-sm font-bold text-secondary-text/60">
                {bin.barNumber}
              </span>
            ))}
          </div>
        </div>

        {/* Right: Stats Summary */}
        <div className="w-full md:w-1/3 flex flex-col justify-end h-64">
          <div className="flex flex-col xl:flex-row items-center xl:items-end justify-center xl:justify-start w-full gap-12">
            
            <div className="flex flex-col items-center md:items-start text-center md:text-left">
              <span className="block text-secondary-text font-medium text-lg mb-1">Average Rating</span>
              <div className="flex flex-col sm:flex-row items-center gap-3">
                <span className="block text-7xl font-bold text-text leading-none">
                  {game.avg_rating.toFixed(1)}
                </span>
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <StarIcon 
                      key={star} 
                      className={`w-6 h-6 sm:w-8 sm:h-8 ${star <= Math.round(game.avg_rating / 2) ? 'text-primary' : 'text-neutral/40'}`}
                    />
                  ))}
                </div>
              </div>
              <span className="block text-secondary-text font-medium text-xs mt-3 w-full text-center md:text-left">
                Based on {game.num_ratings.toLocaleString()} total ratings
              </span>
            </div>

            {/* Gauge Chart for % Recommended */}
            <div className="relative flex flex-col items-center justify-center shrink-0">
              <div className="relative w-32 h-32 flex items-center justify-center">
                {/* SVG Gauge */}
                <svg className="w-full h-full absolute inset-0 transform rotate-[135deg]">
                  {/* Background Arc */}
                  <circle
                    cx="64"
                    cy="64"
                    r={gaugeRadius}
                    stroke="currentColor"
                    strokeWidth="12"
                    fill="transparent"
                    strokeDasharray={`${gaugeArcLength} ${gaugeCircumference}`}
                    className="text-neutral/20"
                    strokeLinecap="round"
                  />
                  {/* Progress Arc */}
                  <circle
                    cx="64"
                    cy="64"
                    r={gaugeRadius}
                    stroke="currentColor"
                    strokeWidth="12"
                    fill="transparent"
                    strokeDasharray={`${progressLength} ${gaugeCircumference}`}
                    className="text-[#00C853] transition-all duration-1000 ease-out"
                    strokeLinecap="round"
                  />
                </svg>
                {/* Center Content */}
                <div className="absolute inset-0 flex flex-col items-center justify-center pt-1">
                  <span className={`${recommendedPercentage === 100 ? 'text-2xl' : 'text-3xl'} font-bold text-[#00C853] leading-none`}>
                    {recommendedPercentage}%
                  </span>
                </div>
                {/* Thumb Icon in the gap */}
                <div className="absolute left-1/2 -translate-x-1/2 top-[94px]">
                  <HandThumbUpIcon className="w-8 h-8 text-[#00C853]" />
                </div>
              </div>
              <div className="flex flex-col items-center mt-3 text-center">
                <span className="text-sm font-bold text-text">Positive Ratings</span>
                <span className="text-[10px] font-medium text-secondary-text uppercase tracking-wider mt-0.5">Scores 7-10</span>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};

const GameRecommendations: React.FC<{ bgg_id: number }> = ({ bgg_id }) => {
  const [model, setModel] = useState('hybrid');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('Content-Based Filtering');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedModel = MODELS.find(m => m.id === model) || MODELS[4];
  
  const { data, isLoading } = useQuery({
    queryKey: ['recommendations', bgg_id, model],
    queryFn: () => fetchRecommendations(bgg_id, model, 10),
  });

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const handleScroll = () => {
    if (scrollContainerRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
      setCanScrollLeft(scrollLeft > 0);
      setCanScrollRight(Math.ceil(scrollLeft) < scrollWidth - clientWidth - 1);
    }
  };

  useEffect(() => {
    handleScroll();
    window.addEventListener('resize', handleScroll);
    return () => window.removeEventListener('resize', handleScroll);
  }, [data]);

  useEffect(() => {
    if (isDropdownOpen) {
      const currentCategory = MODELS.find(m => m.id === model)?.category;
      if (currentCategory) setActiveTab(currentCategory);
    }
  }, [isDropdownOpen, model]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="mt-24 border-t border-neutral/20 pt-16">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <h2 className="text-4xl font-serif text-text">Similar Games</h2>
        
        <div className="relative" ref={dropdownRef}>
          <button 
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="flex items-center gap-1.5 bg-surface border border-neutral text-text font-bold rounded-full px-3 py-1.5 shadow-sm hover:border-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 text-[13px]"
            title="Recommendation Engine Settings"
          >
            <svg className="w-4 h-4 text-secondary-text" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="hidden sm:inline text-secondary-text font-medium">Recommendation Engine: </span>
            <span className="text-primary">{selectedModel.category} | {selectedModel.name}</span>
            <svg className={`w-3 h-3 ml-0.5 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {isDropdownOpen && (
            <div className="absolute right-0 top-full mt-2 w-max min-w-[460px] bg-surface border border-neutral/30 rounded-2xl shadow-xl z-50 overflow-hidden text-sm flex flex-col ring-1 ring-black/5">
              
              {/* Segmented Control / Tabs */}
              <div className="p-3 bg-neutral/5 border-b border-neutral/10">
                <div className="grid grid-cols-2 gap-1 bg-neutral/20 shadow-inner p-1 rounded-xl">
                  {RECSYS_TYPES.map(category => (
                    <button
                      key={category.id}
                      onClick={() => {
                        if (category.available) setActiveTab(category.id);
                      }}
                      className={`text-[11px] font-bold px-3 py-2 rounded-lg transition-all text-center flex items-center justify-center duration-200 ${
                        activeTab === category.id
                          ? 'bg-surface text-primary shadow-[0_1px_3px_rgba(0,0,0,0.1),0_1px_2px_rgba(0,0,0,0.06)] ring-1 ring-black/5'
                          : category.available
                            ? 'text-secondary-text hover:text-text hover:bg-neutral/10'
                            : 'text-secondary-text/40 cursor-not-allowed'
                      }`}
                      disabled={!category.available}
                    >
                      {category.name}
                      {!category.available && <span className="ml-1.5 text-[9px] bg-neutral/20 px-1.5 py-0.5 rounded uppercase tracking-wider shadow-inner">Soon</span>}
                    </button>
                  ))}
                </div>
              </div>

              {/* Dynamic Description for Active Tab */}
              <div className="px-5 py-3.5 bg-neutral/5 border-b border-neutral/10 text-sm text-secondary-text flex items-start gap-2 leading-relaxed">
                <svg className="w-4 h-4 text-secondary-text/70 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {activeTab === 'Popularity-Based' 
                  ? 'Recommendations based on overall community engagement and game ratings.' 
                  : activeTab === 'Content-Based Filtering'
                    ? 'Matches based on game characteristics, mechanics, categories, and designer relationships.'
                    : activeTab === 'Collaborative Filtering'
                      ? 'Matches based on user collections and play history.'
                      : 'A hybrid approach combining multiple recommendation strategies.'}
              </div>

              {/* Models List for Active Tab */}
              <div className="flex flex-col bg-surface min-h-[250px]">
                <div className="grid grid-cols-[1fr_90px_90px] gap-4 px-5 py-3 text-[10px] font-extrabold text-secondary-text uppercase tracking-wider border-b border-neutral/10 bg-surface">
                  <div>Algorithm</div>
                  <div className="text-right" title="Is the system diverse?">Coverage</div>
                  <div className="text-right" title="Are the 10 recommendations different from each other?">ILD@10</div>
                </div>
                
                <div className="overflow-y-auto max-h-[300px]">
                  {MODELS.filter(m => m.category === activeTab).length > 0 ? (
                    MODELS.filter(m => m.category === activeTab).map(m => (
                      <button
                        key={m.id}
                        onClick={() => { setModel(m.id); setIsDropdownOpen(false); }}
                        className={`w-full grid grid-cols-[1fr_90px_90px] gap-4 px-5 py-3 items-center text-left hover:bg-neutral/5 transition-colors ${
                          m.id === model ? 'bg-primary/10 font-bold text-primary' : 'text-text'
                        }`}
                      >
                        <div>{m.name}</div>
                        <div className="text-right text-secondary-text tabular-nums tracking-tight text-xs">
                          {m.coverage ? `${m.coverage.toFixed(2)}%` : '—'}
                        </div>
                        <div className="text-right text-secondary-text tabular-nums tracking-tight text-xs">
                          {m.ild ? m.ild.toFixed(2) : '—'}
                        </div>
                      </button>
                    ))
                  ) : (
                    <div className="p-8 text-center text-secondary-text text-sm">
                      Models for this category are coming soon.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      
      {isLoading ? (
        <div className="flex gap-6 overflow-x-auto pb-8 snap-x">
           {[1,2,3,4,5].map(i => <div key={i} className="min-w-[240px] h-[320px] bg-neutral/10 rounded-2xl animate-pulse snap-start" />)}
        </div>
      ) : data?.recommendations?.length === 0 ? (
        <div className="text-center py-12 text-secondary-text">No recommendations found.</div>
      ) : (
        <div className="relative group">
          {/* Left Blur Indicator */}
          <div className={`absolute left-0 top-0 bottom-8 w-24 bg-gradient-to-r from-surface to-transparent z-10 pointer-events-none transition-opacity duration-300 ${canScrollLeft ? 'opacity-100' : 'opacity-0'}`} />
          
          {/* Right Blur Indicator */}
          <div className={`absolute right-0 top-0 bottom-8 w-24 bg-gradient-to-l from-surface to-transparent z-10 pointer-events-none transition-opacity duration-300 ${canScrollRight ? 'opacity-100' : 'opacity-0'}`} />
          
          <div 
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="flex gap-6 overflow-x-auto pb-8 snap-x" 
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            {data?.recommendations.map(rec => (
            <div key={rec.game.bgg_id || rec.game.id} className="min-w-[300px] max-w-[300px] snap-start flex flex-col gap-3">
              <div className="flex-1">
                <GameCard 
                  game={rec.game as any} 
                  matchPercentage={model === 'popularity' ? undefined : Math.round(rec.score * 100)} 
                />
              </div>
              {/* 
              {rec.reason && rec.reason.length > 0 && (
                <div className="text-xs font-medium text-primary bg-primary/10 border border-primary/20 px-3 py-2 rounded-lg line-clamp-2 leading-relaxed shrink-0 shadow-sm">
                  {rec.reason[0]}
                </div>
              )}
              */}
            </div>
          ))}
          </div>
        </div>
      )}
    </div>
  );
};

const ReviewCard: React.FC<{ review: Review }> = ({ review }) => {
  const [expanded, setExpanded] = useState(false);
  const isLong = review.comment && review.comment.length > 200;

  return (
    <div className="bg-white border border-stone-100 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.05)] p-5 rounded-2xl flex flex-col transition-all hover:shadow-[0_4px_12px_-2px_rgba(0,0,0,0.08)]">
      <div className="flex justify-between items-start mb-3">
        <div className="flex flex-col">
          <span className="font-bold text-text text-sm">{review.user}</span>
          {review.created_at && (
            <span className="text-[11px] font-medium text-secondary-text/80 uppercase tracking-wider mt-0.5">
              {new Date(review.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
            </span>
          )}
        </div>
        {review.rating !== null && review.rating !== undefined && (
          <div className="flex items-center gap-1">
            <StarIcon className="w-4 h-4 text-[#FFB400]" />
            <span className="font-bold text-text text-sm">{review.rating}/10</span>
          </div>
        )}
      </div>
      {review.comment && (
        <div className="flex-1 flex flex-col mt-1">
          <p className={`text-secondary-text text-sm leading-relaxed whitespace-pre-wrap ${!expanded ? 'line-clamp-4' : ''}`}>
            {review.comment}
          </p>
          {isLong && (
            <button 
              onClick={() => setExpanded(!expanded)}
              className="text-primary text-xs font-bold self-start mt-2 hover:underline transition-colors"
            >
              {expanded ? 'Show less' : 'Read more'}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

const GameReviews: React.FC<{ game: Game }> = ({ game }) => {
  const [page, setPage] = useState(1);
  const [ratingFilter, setRatingFilter] = useState<'all' | 'positive' | 'mixed' | 'negative'>('all');
  const [languageFilter, setLanguageFilter] = useState<string>('en');
  const [isLangOpen, setIsLangOpen] = useState(false);
  const [isRatingOpen, setIsRatingOpen] = useState(false);
  
  const langRef = useRef<HTMLDivElement>(null);
  const ratingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (langRef.current && !langRef.current.contains(event.target as Node)) setIsLangOpen(false);
      if (ratingRef.current && !ratingRef.current.contains(event.target as Node)) setIsRatingOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const pageSize = 4;
  
  // Calculate min/max based on filter
  let minRating: number | undefined;
  let maxRating: number | undefined;
  if (ratingFilter === 'positive') { minRating = 7; maxRating = 10; }
  else if (ratingFilter === 'mixed') { minRating = 4; maxRating = 6.99; }
  else if (ratingFilter === 'negative') { minRating = 0; maxRating = 3.99; }
  
  const language = languageFilter === 'all' ? undefined : languageFilter;
  
  const { data, isLoading, isError, error, isPlaceholderData } = useQuery({
    queryKey: ['reviews', game.bgg_id, page, ratingFilter, languageFilter],
    queryFn: () => fetchReviews(game.bgg_id, page, pageSize, minRating, maxRating, language),
    placeholderData: keepPreviousData,
  });

  const handleRatingChange = (filter: 'all' | 'positive' | 'mixed' | 'negative') => {
    setRatingFilter(filter);
    setPage(1);
  };

  const handleLanguageChange = (filter: string) => {
    setLanguageFilter(filter);
    setPage(1);
  };

  const languageOptions = useMemo(() => {
    if (!data?.language_breakdown) return [{ id: 'all', label: 'All Languages', pct: undefined }];
    
    const languageNames = new Intl.DisplayNames(['en'], { type: 'language' });
    
    const langs = Object.entries(data.language_breakdown)
      .sort((a, b) => b[1] - a[1])
      .map(([code, pct]) => {
        let label = code;
        try { label = languageNames.of(code) || code; } catch (e) {}
        return { id: code, label, pct };
      });
      
    return [{ id: 'all', label: 'All Languages', pct: undefined }, ...langs];
  }, [data?.language_breakdown]);

  const currentLangLabel = languageOptions.find(o => o.id === languageFilter)?.label || 'All Languages';

  const ratingOptions = useMemo(() => {
    return [
      { id: 'all', label: 'All Ratings', min: '', max: '', pct: 100 },
      { id: 'positive', label: 'Positive', min: '7.0', max: '10.0', pct: data?.rating_breakdown?.positive ?? 0 },
      { id: 'mixed', label: 'Mixed', min: '4.0', max: '6.9', pct: data?.rating_breakdown?.mixed ?? 0 },
      { id: 'negative', label: 'Negative', min: '1.0', max: '3.9', pct: data?.rating_breakdown?.negative ?? 0 }
    ];
  }, [data?.rating_breakdown]);

  if (!game.num_comments && !game.num_ratings) return null;

  return (
    <div className="mt-24 border-t border-neutral/20 pt-16">
      <div className="flex flex-col mb-8">
        <h2 className="text-4xl font-serif text-text mb-2">Reviews</h2>
        {data?.total !== undefined && (
          <span className="text-lg font-bold text-secondary-text">
            {data.total.toLocaleString()} reviews
          </span>
        )}
      </div>
      
      <CommunityConsensus gameId={game.bgg_id} summary={game.customer_summary} />

      <div className="flex flex-col lg:flex-row lg:items-center justify-between mb-6 mt-4 gap-4">
        <div className="flex items-baseline gap-3">
          <h3 className="text-2xl font-serif text-text">User Reviews</h3>
        </div>
        
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Language Filter */}
          <div className="relative" ref={langRef}>
            <button 
              onClick={() => { setIsLangOpen(!isLangOpen); setIsRatingOpen(false); }}
              className="flex items-center justify-between w-full sm:w-auto gap-1.5 bg-surface border border-neutral/50 text-text font-bold rounded-full px-3 py-2 shadow-sm hover:border-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 text-[13px]"
            >
              <LanguageIcon className="w-4 h-4 text-secondary-text mr-1" />
              <span className="tracking-wide">{languageFilter.toUpperCase()}</span>
              <svg className={`w-3.5 h-3.5 ml-1 transition-transform ${isLangOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {isLangOpen && (
              <div className="absolute left-0 sm:right-0 sm:left-auto top-full mt-2 w-full sm:w-64 bg-surface border border-neutral/30 rounded-2xl shadow-xl z-50 overflow-hidden text-sm flex flex-col ring-1 ring-black/5 py-1 max-h-80 overflow-y-auto">
                {languageOptions.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => { handleLanguageChange(opt.id); setIsLangOpen(false); }}
                    className={`text-left px-4 py-2.5 hover:bg-neutral/5 transition-colors font-semibold flex justify-between items-center ${languageFilter === opt.id ? 'text-primary bg-primary/5' : 'text-text'}`}
                  >
                    <span>{opt.label}</span>
                    {opt.pct !== undefined && (
                      <span className="text-secondary-text text-[12px] font-medium ml-4">{opt.pct}%</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Rating Filter */}
          <div className="relative" ref={ratingRef}>
            <button 
              onClick={() => { setIsRatingOpen(!isRatingOpen); setIsLangOpen(false); }}
              className="flex items-center justify-between w-full sm:w-auto gap-1.5 bg-surface border border-neutral/50 text-text font-bold rounded-full px-3 py-2 shadow-sm hover:border-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 text-[13px]"
            >
              <StarIcon className="w-4 h-4 text-secondary-text mr-1" />
              <span className="capitalize tracking-wide">
                {ratingFilter === 'all' ? 'All Ratings' : ratingFilter}
              </span>
              <svg className={`w-3.5 h-3.5 ml-1 transition-transform ${isRatingOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {isRatingOpen && (
              <div className="absolute right-0 sm:left-auto top-full mt-2 w-full sm:w-[340px] bg-surface border border-neutral/30 rounded-2xl shadow-xl z-50 overflow-hidden text-sm flex flex-col ring-1 ring-black/5 py-2">
                <div className="grid grid-cols-[3fr_1fr_1fr_1.5fr] gap-2 px-4 py-1.5 text-[11px] font-bold text-secondary-text uppercase tracking-wider border-b border-neutral/10 mb-1">
                  <span>Rating</span>
                  <span className="text-center">Min</span>
                  <span className="text-center">Max</span>
                  <span className="text-right">Reviews</span>
                </div>
                {ratingOptions.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => { handleRatingChange(opt.id as any); setIsRatingOpen(false); }}
                    className={`grid grid-cols-[3fr_1fr_1fr_1.5fr] gap-2 items-center text-left px-4 py-2.5 hover:bg-neutral/5 transition-colors font-semibold ${ratingFilter === opt.id ? 'text-primary bg-primary/5' : 'text-text'}`}
                  >
                    <span>{opt.label}</span>
                    <span className="text-center text-secondary-text">{opt.min || '-'}</span>
                    <span className="text-center text-secondary-text">{opt.max || '-'}</span>
                    <span className="text-right font-medium text-secondary-text">{opt.pct}%</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {isLoading && page === 1 ? (
        <div className="space-y-6 animate-pulse">
           {[1, 2, 3].map(i => (
             <div key={i} className="bg-surface border border-neutral/20 p-6 rounded-2xl h-32" />
           ))}
        </div>
      ) : isError ? (
        <div className="text-secondary-text">Failed to load reviews.</div>
      ) : data?.items?.length === 0 ? (
        <div className="text-secondary-text">No reviews available for this game.</div>
      ) : (
        <div className={`grid grid-cols-1 md:grid-cols-2 gap-4 transition-opacity duration-300 ${isPlaceholderData ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
          {data?.items.map(review => (
            <ReviewCard key={review.id} review={review} />
          ))}

          {/* Pagination Controls */}
          {data?.total !== undefined && data.total > pageSize && (
            <div className="col-span-1 md:col-span-2 flex justify-center items-center gap-4 mt-6 pt-4">
              <button
                disabled={page === 1}
                onClick={() => setPage(p => Math.max(1, p - 1))}
                className="px-4 py-2 bg-white border border-stone-200 rounded-full text-xs font-bold text-text disabled:opacity-30 hover:bg-neutral/5 transition-colors shadow-sm"
              >
                Previous
              </button>
              <span className="text-xs font-medium text-secondary-text tracking-wider uppercase">
                Page {page} of {Math.ceil(data.total / pageSize)}
              </span>
              <button
                disabled={page >= Math.ceil(data.total / pageSize)}
                onClick={() => setPage(p => p + 1)}
                className="px-4 py-2 bg-white border border-stone-200 rounded-full text-xs font-bold text-text disabled:opacity-30 hover:bg-neutral/5 transition-colors shadow-sm"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// --- Types for ABSA ---
interface AspectAggregate {
  aspect: string;
  positive_count: number;
  negative_count: number;
  mixed_count: number;
  neutral_count: number;
  total_mentions: number;
  mean_sentiment: number;
  evidence_samples: string[];
}

// --- ABSA Component ---
const CommunityConsensus = ({ gameId, summary }: { gameId: number, summary?: string }) => {
  const [aspects, setAspects] = useState<AspectAggregate[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    const fetchAspects = async () => {
      try {
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const response = await axios.get(`${baseUrl}/api/games/${gameId}/aspects`);
        setAspects(response.data);
      } catch (err) {
        console.error("Failed to fetch ABSA stats:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchAspects();
  }, [gameId]);

  if (loading) return null;
  if (!summary || aspects.length === 0) return null;

  return (
    <div className="mb-12">
      <div className="mb-6">
        <h3 className="text-2xl font-serif text-text mb-2">Community Consensus</h3>
        <div className="flex items-center gap-2 text-sm font-medium text-secondary-text">
          <SparklesIcon className="w-5 h-5 text-yellow-500" />
          <span>Generated from text of user reviews</span>
        </div>
      </div>

      <div className="bg-white border border-stone-200/60 rounded-2xl p-5 mb-8 shadow-sm">
        <p className="text-text leading-relaxed text-sm md:text-base italic">
          "{summary}"
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {(showAll ? aspects : aspects.slice(0, 6)).map((agg, idx) => {
          // Determine sentiment class
          const posRatio = agg.positive_count / Math.max(1, agg.total_mentions);
          const isPositive = posRatio >= 0.5;
          const Icon = isPositive ? HandThumbUpIcon : HandThumbDownIcon;

          const gaugeRadius = 24;
          const gaugeCircumference = 2 * Math.PI * gaugeRadius;
          const gaugeArcLength = gaugeCircumference * 0.75;
          const progressLength = posRatio * gaugeArcLength;

          return (
            <div key={idx} className="bg-white border border-stone-200/60 rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-primary/30 transition-all relative group">
              <div className="flex items-start gap-4 mb-3">
                {/* Mini Gauge Chart */}
                <div className="relative w-14 h-14 flex items-center justify-center shrink-0">
                  <svg className="w-full h-full absolute inset-0 transform rotate-[135deg]">
                    <circle
                      cx="28" cy="28" r={gaugeRadius} stroke="currentColor" strokeWidth="4" fill="transparent"
                      strokeDasharray={`${gaugeArcLength} ${gaugeCircumference}`}
                      className="text-stone-100" strokeLinecap="round"
                    />
                    <circle
                      cx="28" cy="28" r={gaugeRadius} stroke="currentColor" strokeWidth="4" fill="transparent"
                      strokeDasharray={`${progressLength} ${gaugeCircumference}`}
                      className={`${isPositive ? 'text-[#00C853]' : 'text-red-500'} transition-all duration-1000 ease-out`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center pt-0.5">
                    <span className={`text-[13px] font-bold ${isPositive ? 'text-[#00C853]' : 'text-red-500'} leading-none`}>
                      {Math.round(posRatio * 100)}%
                    </span>
                  </div>
                  {/* Thumb Icon in the gap */}
                  <div className="absolute left-1/2 -translate-x-1/2 top-[44px]">
                    <Icon className={`w-[14px] h-[14px] ${isPositive ? 'text-[#00C853]' : 'text-red-500'}`} />
                  </div>
                </div>

                <div className="flex flex-col justify-center h-14">
                  <h3 className="font-bold text-[17px] text-text leading-tight group-hover:text-primary transition-colors">{agg.aspect}</h3>
                  <span className="text-[11px] font-bold text-secondary-text mt-1 uppercase tracking-wider">
                    {isPositive ? 'Positive Feedback' : 'Positive Feedback'}
                  </span>
                </div>
              </div>

              <div className="flex flex-col gap-1.5 mt-2">
                <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider pl-1.5">
                  Based on {agg.total_mentions} {agg.total_mentions === 1 ? 'mention' : 'mentions'}
                </div>
                <div className="relative bg-stone-50/80 rounded-xl p-3 border border-stone-100">
                  <ChatBubbleLeftRightIcon className="w-4 h-4 text-stone-300 absolute top-3 left-3" />
                  <p className="text-[13px] text-text italic leading-relaxed pl-6 line-clamp-3">
                    "{agg.evidence_samples[0] || 'Various feedback.'}"
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {aspects.length > 6 && (
        <div className="mt-8 flex justify-center">
          <button
            onClick={() => setShowAll(!showAll)}
            className="px-6 py-2.5 bg-white border border-stone-200 rounded-full text-sm font-bold text-text hover:bg-stone-50 transition-colors shadow-sm flex items-center gap-2"
          >
            {showAll ? 'Show less' : `Show more consensus (${aspects.length - 6} more)`}
          </button>
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
        <Link to="/games" className="pointer-events-auto bg-white/80 backdrop-blur-md px-4 py-2 shadow-sm border border-neutral/20 flex items-center gap-1.5 rounded-full text-primary font-bold text-sm hover:opacity-80 transition-opacity">
          <ArrowLeftIcon className="w-4 h-4" />
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

          <div className="flex flex-wrap items-center gap-3 mb-3">
            {game.categories && game.categories.map(cat => (
               <span key={cat} className="px-4 py-2 bg-neutral/20 text-text rounded-full text-sm font-bold whitespace-nowrap">
                 {CATEGORY_MAP[cat] || cat}
               </span>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {game.themes && game.themes.map(theme => (
               <span key={theme} className="px-3 py-1 bg-transparent border border-neutral/40 text-secondary-text rounded-full text-xs font-medium whitespace-nowrap">
                 {theme}
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
        {/* Description and Mechanics */}
        <div className="lg:col-span-2">
          <div className="mb-12">
            <h2 className="text-4xl font-serif text-text mb-6">About the Game</h2>
            <div 
              className="text-lg text-secondary-text leading-relaxed space-y-5"
              dangerouslySetInnerHTML={{ __html: cleanDescription }}
            />
          </div>

          {game.mechanics && game.mechanics.length > 0 && (
            <div>
              <h3 className="text-2xl font-serif text-text mb-4">Mechanics</h3>
              <ExpandableChipList items={game.mechanics} limit={8} />
            </div>
          )}
        </div>

        {/* Sidebar Entities */}
        <div className="space-y-10">
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

      {/* Game Distributions (Stats) */}
      <GameDistributions game={game} />

      {/* Rankings */}
      <GameRankings game={game} />

      {/* User Ratings */}
      <UserRatings game={game} />

      {/* Reviews (Includes Community Consensus) */}
      <GameReviews game={game} />

      {/* Recommendations (Similar Games) */}
      <GameRecommendations bgg_id={game.bgg_id} />
    </div>
  );
};
