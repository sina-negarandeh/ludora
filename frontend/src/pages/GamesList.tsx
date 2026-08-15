import React, { useState, useEffect } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { fetchGames, fetchCategories, fetchMechanics, fetchSearch } from '../api/games';
import type { GameQuery, SearchQueryPayload } from '../api/games';
import { GameCard } from '../components/GameCard';
import { MultiSelectDropdown } from '../components/MultiSelectDropdown';
import { SearchableCombobox } from '../components/SearchableCombobox';

export const GamesList: React.FC = () => {
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [showAdvancedPlayers, setShowAdvancedPlayers] = useState(false);
  const [searchMode, setSearchMode] = useState<'lexical' | 'semantic' | 'hybrid'>('hybrid');
  const [openDropdown, setOpenDropdown] = useState<'searchMode' | 'sort' | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!(event.target as Element).closest('.dropdown-container')) {
        setOpenDropdown(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  const [query, setQuery] = useState<GameQuery>({
    sort_by: 'rank',
    order: 'asc',
    skip: 0,
    limit: 24
  });
  
  const pageSize = query.limit || 24;
  const page = (query.skip || 0) / pageSize;

  const activeFiltersCount = 
    (query.categories?.length || 0) +
    (query.mechanics?.length || 0) +
    (query.exact_players !== undefined ? 1 : 0) +
    (query.min_players !== undefined ? 1 : 0) +
    (query.max_players !== undefined ? 1 : 0) +
    (query.min_weight !== undefined && query.min_weight > 1.0 ? 1 : 0) +
    (query.max_weight !== undefined && query.max_weight < 5.0 ? 1 : 0);

  const { data: categories } = useQuery({ queryKey: ['categories'], queryFn: fetchCategories, staleTime: Infinity });
  const { data: mechanics } = useQuery({ queryKey: ['mechanics'], queryFn: fetchMechanics, staleTime: Infinity });

  const { data, isLoading, isError } = useQuery({
    queryKey: ['games', query, searchMode],
    queryFn: () => {
      if (query.query) {
        const searchPayload: SearchQueryPayload = {
          q: query.query,
          mode: searchMode,
          filters: {
            categories: query.categories,
            mechanics: query.mechanics,
            exact_players: query.exact_players,
            min_players: query.min_players,
            max_players: query.max_players,
            min_weight: query.min_weight,
            max_weight: query.max_weight,
          }
        };
        return fetchSearch(searchPayload, query.skip, query.limit);
      }
      return fetchGames(query);
    },
    staleTime: 60000,
    placeholderData: keepPreviousData,
  });

  const handleFilterChange = (key: keyof GameQuery, value: any) => {
    setQuery(prev => {
      const newQuery = { ...prev, skip: 0 };
      if (value === '' || value === undefined || (typeof value === 'number' && isNaN(value)) || (Array.isArray(value) && value.length === 0)) {
        delete newQuery[key];
      } else {
        newQuery[key] = value;
      }
      return newQuery;
    });
  };

  const handlePageChange = (newPage: number) => {
    setQuery(prev => ({ ...prev, skip: newPage * pageSize }));
  };

  const clearFilters = () => setQuery({ sort_by: query.sort_by, order: query.order, skip: 0, limit: pageSize });

  return (
    <div className="w-full px-4 pt-12 lg:pt-24 pb-8 flex gap-6 lg:gap-8 items-start relative">
      
      {/* Mobile Pill Overlay */}
      {!isSidebarOpen && (
        <button 
          onClick={() => setSidebarOpen(true)}
          className="fixed bottom-24 right-6 z-50 bg-white/90 backdrop-blur-md px-6 shadow-lg border border-neutral/20 flex items-center justify-center gap-2 h-[4rem] rounded-full text-primary font-bold hover:opacity-80 transition-opacity lg:hidden"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
          </svg>
          <span>Filters</span>
          {activeFiltersCount > 0 && (
            <>
              <div className="w-px h-5 bg-primary/30 mx-1"></div>
              <span>{activeFiltersCount}</span>
            </>
          )}
        </button>
      )}

      {/* Desktop Sidebar Container */}
      <div className={`hidden lg:block sticky top-24 z-10 transition-all duration-300 flex-shrink-0 ${isSidebarOpen ? 'w-[280px] opacity-100' : 'w-0 opacity-0 overflow-hidden'}`}>
        <aside className="w-[280px] bg-white/80 backdrop-blur-xl border border-neutral/20 shadow-sm rounded-3xl p-6 flex flex-col h-[calc(100vh-8rem)] animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-serif text-text font-bold">Filters</h3>
              <button onClick={() => setSidebarOpen(false)} className="p-1.5 rounded-full hover:bg-neutral/10 text-secondary-text hover:text-text transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 space-y-6 custom-scrollbar">
              
              {/* Category */}
              <div>
                <label className="block text-sm font-bold text-secondary-text mb-2">Category</label>
                <MultiSelectDropdown 
                  options={categories || []} 
                  selected={query.categories || []} 
                  onChange={(selected) => handleFilterChange('categories', selected)} 
                  placeholder="All Categories" 
                />
              </div>

              {/* Mechanic */}
              <div>
                <label className="block text-sm font-bold text-secondary-text mb-2">Mechanic</label>
                <SearchableCombobox 
                  options={mechanics || []} 
                  selected={query.mechanics || []} 
                  onChange={(selected) => handleFilterChange('mechanics', selected)} 
                  placeholder="Search mechanics..." 
                />
              </div>

              {/* Players */}
              <div>
                 <label className="block text-sm font-bold text-secondary-text mb-2">Players</label>
                 
                 <div className="flex flex-wrap gap-2">
                   {[
                     { label: 'Any', value: undefined },
                     { label: '1 (Solo)', value: 1 },
                     { label: '2', value: 2 },
                     { label: '3', value: 3 },
                     { label: '4', value: 4 },
                     { label: '5', value: 5 },
                     { label: '6+', value: 6 },
                   ].map(opt => (
                     <button
                       key={opt.label}
                       onClick={() => {
                         handleFilterChange('exact_players', opt.value);
                         handleFilterChange('min_players', undefined);
                         handleFilterChange('max_players', undefined);
                       }}
                       className={`px-3 py-1.5 rounded-full text-sm font-bold transition-colors ${query.exact_players === opt.value && query.min_players === undefined && query.max_players === undefined ? 'bg-primary text-white shadow-md' : 'bg-neutral/10 text-secondary-text hover:bg-neutral/20'}`}
                     >
                       {opt.label}
                     </button>
                   ))}
                 </div>

                 <button 
                   onClick={() => setShowAdvancedPlayers(!showAdvancedPlayers)} 
                   className="mt-3 text-xs text-secondary-text font-medium hover:text-primary transition-colors flex items-center gap-1"
                 >
                   <span>Specify Min/Max</span>
                   <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className={`w-3 h-3 transition-transform ${showAdvancedPlayers ? 'rotate-180' : ''}`}><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>
                 </button>

                 <div className={`overflow-hidden transition-all duration-300 ${showAdvancedPlayers ? 'max-h-24 opacity-100 mt-2' : 'max-h-0 opacity-0'}`}>
                   <div className="flex items-center gap-2">
                     <input type="number" min="1" placeholder="Min" value={query.min_players || ''} onChange={(e) => { handleFilterChange('min_players', parseInt(e.target.value)); handleFilterChange('exact_players', undefined); }} className="w-full bg-neutral/10 border-none rounded-xl px-3 py-2 text-text focus:ring-2 focus:ring-primary/50 outline-none" />
                     <span className="text-secondary-text">-</span>
                     <input type="number" min="1" placeholder="Max" value={query.max_players || ''} onChange={(e) => { handleFilterChange('max_players', parseInt(e.target.value)); handleFilterChange('exact_players', undefined); }} className="w-full bg-neutral/10 border-none rounded-xl px-3 py-2 text-text focus:ring-2 focus:ring-primary/50 outline-none" />
                   </div>
                 </div>
              </div>

              {/* Complexity */}
              <div>
                 <label className="block text-sm font-bold text-secondary-text mb-3">Complexity (1.0 - 5.0)</label>
                 
                 <div className="flex flex-wrap gap-2 mb-4">
                   {[
                     { label: 'Light (1-2)', min: 1.0, max: 2.0 },
                     { label: 'Medium (2-3.5)', min: 2.0, max: 3.5 },
                     { label: 'Heavy (3.5-5)', min: 3.5, max: 5.0 },
                   ].map(preset => (
                     <button
                       key={preset.label}
                       onClick={() => {
                         handleFilterChange('min_weight', preset.min);
                         handleFilterChange('max_weight', preset.max);
                       }}
                       className={`px-3 py-1.5 rounded-full text-xs font-bold transition-colors ${query.min_weight === preset.min && query.max_weight === preset.max ? 'bg-primary text-white shadow-md' : 'bg-neutral/10 text-secondary-text hover:bg-neutral/20'}`}
                     >
                       {preset.label}
                     </button>
                   ))}
                 </div>

                 <div className="flex items-center gap-3">
                   <span className="text-sm font-bold text-secondary-text min-w-[1.5rem] text-right">
                     {(query.min_weight || 1.0).toFixed(1)}
                   </span>
                   
                   <div className="relative w-full h-8 flex items-center">
                     <div className="absolute w-full h-1.5 bg-neutral/20 rounded-full" />
                     <div 
                       className="absolute h-1.5 bg-primary rounded-full pointer-events-none" 
                       style={{ 
                         left: `${(((query.min_weight || 1.0) - 1.0) / 4.0) * 100}%`,
                         width: `${(((query.max_weight || 5.0) - (query.min_weight || 1.0)) / 4.0) * 100}%` 
                       }} 
                     />
                     <input 
                       type="range" min="1.0" max="5.0" step="0.1" value={query.min_weight || 1.0}
                       onChange={(e) => {
                         const val = Math.min(parseFloat(e.target.value), (query.max_weight || 5.0));
                         handleFilterChange('min_weight', val);
                       }}
                       className={`absolute w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-primary [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:cursor-grab active:[&::-webkit-slider-thumb]:cursor-grabbing [&::-moz-range-thumb]:pointer-events-auto ${(query.min_weight || 1.0) > 3.0 ? 'z-20' : 'z-10'}`}
                     />
                     <input 
                       type="range" min="1.0" max="5.0" step="0.1" value={query.max_weight || 5.0}
                       onChange={(e) => {
                         const val = Math.max(parseFloat(e.target.value), (query.min_weight || 1.0));
                         handleFilterChange('max_weight', val);
                       }}
                       className={`absolute w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-primary [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:cursor-grab active:[&::-webkit-slider-thumb]:cursor-grabbing [&::-moz-range-thumb]:pointer-events-auto ${(query.min_weight || 1.0) > 3.0 ? 'z-10' : 'z-20'}`}
                     />
                   </div>

                   <span className="text-sm font-bold text-secondary-text min-w-[1.5rem]">
                     {(query.max_weight || 5.0).toFixed(1)}
                   </span>
                 </div>
              </div>

            </div>

            <div className="pt-6 border-t border-neutral/20 mt-4">
               <button onClick={clearFilters} className="w-full py-3 rounded-xl bg-neutral/20 text-text font-bold hover:bg-neutral/30 transition-colors">
                  Clear All Filters
               </button>
            </div>
          </aside>
      </div>

      {/* Floating Desktop Filters Button (when sidebar is closed) */}
      {!isSidebarOpen && (
        <div className="fixed top-24 left-4 lg:left-8 z-40 hidden lg:flex pointer-events-none">
          <button 
            onClick={() => setSidebarOpen(true)}
            className="pointer-events-auto bg-white/80 backdrop-blur-md px-5 py-2.5 shadow-lg border border-neutral/20 flex items-center justify-center gap-2 rounded-full text-primary font-bold hover:bg-neutral/5 transition-colors animate-in fade-in zoom-in-95 duration-200"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
            </svg>
            <span>Filters</span>
            {activeFiltersCount > 0 && (
              <>
                <div className="w-px h-4 bg-primary/30 mx-0.5"></div>
                <span>{activeFiltersCount}</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Mobile Full Screen Sidebar (When Open) */}
      {isSidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden bg-white/95 backdrop-blur-2xl p-6 flex flex-col h-screen overflow-y-auto">
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-3xl font-serif text-text font-bold">Filters</h3>
            <button onClick={() => setSidebarOpen(false)} className="p-2 bg-neutral/10 rounded-full text-secondary-text">
               <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-8 h-8"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
          
          <div className="flex-1 space-y-8">
              {/* Category */}
              <div>
                <label className="block text-lg font-bold text-secondary-text mb-3">Category</label>
                <MultiSelectDropdown 
                  options={categories || []} 
                  selected={query.categories || []} 
                  onChange={(selected) => handleFilterChange('categories', selected)} 
                  placeholder="All Categories" 
                />
              </div>

              {/* Mechanic */}
              <div>
                <label className="block text-lg font-bold text-secondary-text mb-3">Mechanic</label>
                <SearchableCombobox 
                  options={mechanics || []} 
                  selected={query.mechanics || []} 
                  onChange={(selected) => handleFilterChange('mechanics', selected)} 
                  placeholder="Search mechanics..." 
                />
              </div>

              {/* Players */}
              <div>
                 <label className="block text-lg font-bold text-secondary-text mb-3">Players</label>
                 
                 <div className="flex flex-wrap gap-3">
                   {[
                     { label: 'Any', value: undefined },
                     { label: '1 (Solo)', value: 1 },
                     { label: '2', value: 2 },
                     { label: '3', value: 3 },
                     { label: '4', value: 4 },
                     { label: '5', value: 5 },
                     { label: '6+', value: 6 },
                   ].map(opt => (
                     <button
                       key={opt.label}
                       onClick={() => {
                         handleFilterChange('exact_players', opt.value);
                         handleFilterChange('min_players', undefined);
                         handleFilterChange('max_players', undefined);
                       }}
                       className={`px-4 py-2 rounded-full text-base font-bold transition-colors ${query.exact_players === opt.value && query.min_players === undefined && query.max_players === undefined ? 'bg-primary text-white shadow-md' : 'bg-neutral/10 text-secondary-text hover:bg-neutral/20'}`}
                     >
                       {opt.label}
                     </button>
                   ))}
                 </div>

                 <button 
                   onClick={() => setShowAdvancedPlayers(!showAdvancedPlayers)} 
                   className="mt-4 text-sm text-secondary-text font-medium hover:text-primary transition-colors flex items-center gap-1"
                 >
                   <span>Specify Min/Max</span>
                   <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className={`w-4 h-4 transition-transform ${showAdvancedPlayers ? 'rotate-180' : ''}`}><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>
                 </button>

                 <div className={`overflow-hidden transition-all duration-300 ${showAdvancedPlayers ? 'max-h-24 opacity-100 mt-3' : 'max-h-0 opacity-0'}`}>
                   <div className="flex items-center gap-3">
                     <input type="number" min="1" placeholder="Min" value={query.min_players || ''} onChange={(e) => { handleFilterChange('min_players', parseInt(e.target.value)); handleFilterChange('exact_players', undefined); }} className="w-full bg-neutral/10 border-none rounded-2xl px-6 py-4 text-lg text-text focus:ring-2 focus:ring-primary/50 outline-none" />
                     <span className="text-secondary-text">-</span>
                     <input type="number" min="1" placeholder="Max" value={query.max_players || ''} onChange={(e) => { handleFilterChange('max_players', parseInt(e.target.value)); handleFilterChange('exact_players', undefined); }} className="w-full bg-neutral/10 border-none rounded-2xl px-6 py-4 text-lg text-text focus:ring-2 focus:ring-primary/50 outline-none" />
                   </div>
                 </div>
              </div>

              {/* Complexity */}
              <div>
                 <label className="block text-lg font-bold text-secondary-text mb-4">Complexity (1.0 - 5.0)</label>
                 
                 <div className="flex flex-wrap gap-3 mb-6">
                   {[
                     { label: 'Light (1-2)', min: 1.0, max: 2.0 },
                     { label: 'Medium (2-3.5)', min: 2.0, max: 3.5 },
                     { label: 'Heavy (3.5-5)', min: 3.5, max: 5.0 },
                   ].map(preset => (
                     <button
                       key={preset.label}
                       onClick={() => {
                         handleFilterChange('min_weight', preset.min);
                         handleFilterChange('max_weight', preset.max);
                       }}
                       className={`px-4 py-2 rounded-full text-sm font-bold transition-colors ${query.min_weight === preset.min && query.max_weight === preset.max ? 'bg-primary text-white shadow-md' : 'bg-neutral/10 text-secondary-text hover:bg-neutral/20'}`}
                     >
                       {preset.label}
                     </button>
                   ))}
                 </div>

                 <div className="flex items-center gap-4 px-2">
                   <span className="text-lg font-bold text-secondary-text min-w-[2rem] text-right">
                     {(query.min_weight || 1.0).toFixed(1)}
                   </span>
                   
                   <div className="relative w-full h-10 flex items-center">
                     <div className="absolute w-full h-2 bg-neutral/20 rounded-full" />
                     <div 
                       className="absolute h-2 bg-primary rounded-full pointer-events-none" 
                       style={{ 
                         left: `${(((query.min_weight || 1.0) - 1.0) / 4.0) * 100}%`,
                         width: `${(((query.max_weight || 5.0) - (query.min_weight || 1.0)) / 4.0) * 100}%` 
                       }} 
                     />
                     <input 
                       type="range" min="1.0" max="5.0" step="0.1" value={query.min_weight || 1.0}
                       onChange={(e) => {
                         const val = Math.min(parseFloat(e.target.value), (query.max_weight || 5.0));
                         handleFilterChange('min_weight', val);
                       }}
                       className={`absolute w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-6 [&::-webkit-slider-thumb]:h-6 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:border-[3px] [&::-webkit-slider-thumb]:border-primary [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:cursor-grab active:[&::-webkit-slider-thumb]:cursor-grabbing [&::-moz-range-thumb]:pointer-events-auto ${(query.min_weight || 1.0) > 3.0 ? 'z-20' : 'z-10'}`}
                     />
                     <input 
                       type="range" min="1.0" max="5.0" step="0.1" value={query.max_weight || 5.0}
                       onChange={(e) => {
                         const val = Math.max(parseFloat(e.target.value), (query.min_weight || 1.0));
                         handleFilterChange('max_weight', val);
                       }}
                       className={`absolute w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-6 [&::-webkit-slider-thumb]:h-6 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:border-[3px] [&::-webkit-slider-thumb]:border-primary [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:cursor-grab active:[&::-webkit-slider-thumb]:cursor-grabbing [&::-moz-range-thumb]:pointer-events-auto ${(query.min_weight || 1.0) > 3.0 ? 'z-10' : 'z-20'}`}
                     />
                   </div>

                   <span className="text-lg font-bold text-secondary-text min-w-[2rem]">
                     {(query.max_weight || 5.0).toFixed(1)}
                   </span>
                 </div>
              </div>
          </div>
          
          <div className="pt-8 mt-8 border-t border-neutral/20">
            <button onClick={() => { setSidebarOpen(false); }} className="w-full py-4 rounded-2xl bg-primary text-white font-bold text-lg">
              Show Results
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 min-w-0 transition-all duration-300">
        {/* Top Right Controls (Search & Sort) */}
        {/* Top Right Controls (Search & Sort) */}
        <div className="fixed top-24 right-4 lg:right-8 z-40 pointer-events-none flex flex-row items-center justify-end gap-3 w-full max-w-[calc(100vw-32px)]">
          
          {/* Search Bar */}
          <div className="pointer-events-auto flex-1 min-w-[200px] sm:min-w-[300px] max-w-[400px] bg-white/80 backdrop-blur-md border border-neutral/20 rounded-full shadow-lg flex items-center p-1.5 gap-2 transition-all focus-within:ring-2 focus-within:ring-primary/30">
            <div className="flex-1 flex items-center pl-4">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5 text-secondary-text">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <input
                type="text"
                placeholder="Search games..."
                value={query.query || ''}
                onChange={(e) => handleFilterChange('query', e.target.value)}
                className="w-full bg-transparent border-none text-text font-medium px-3 py-2 outline-none placeholder-secondary-text/60"
              />
            </div>
            
            <div className="w-px h-6 bg-neutral/20 hidden sm:block"></div>
            
            <div className="relative hidden sm:flex items-center pr-2 dropdown-container">
              <button
                onClick={() => setOpenDropdown(openDropdown === 'searchMode' ? null : 'searchMode')}
                className="bg-transparent border-none text-primary font-bold text-sm focus:ring-0 cursor-pointer py-2 pl-3 pr-8 outline-none hover:bg-neutral/5 transition-colors rounded-full text-left flex items-center relative"
              >
                {searchMode.charAt(0).toUpperCase() + searchMode.slice(1)}
              </button>
              <div className="absolute right-3 pointer-events-none text-primary">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className={`w-3.5 h-3.5 transition-transform ${openDropdown === 'searchMode' ? 'rotate-180' : ''}`}><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>
              </div>
              
              {openDropdown === 'searchMode' && (
                <div className="absolute top-[calc(100%+16px)] right-0 w-36 bg-white/95 backdrop-blur-md border border-neutral/20 rounded-2xl shadow-xl z-50 overflow-hidden text-sm flex flex-col ring-1 ring-black/5 p-1">
                  {['lexical', 'semantic', 'hybrid'].map(mode => (
                    <button
                      key={mode}
                      onClick={() => {
                        setSearchMode(mode as any);
                        setOpenDropdown(null);
                      }}
                      className={`text-left px-4 py-2.5 rounded-xl font-medium transition-colors ${
                        searchMode === mode 
                          ? 'bg-primary/10 text-primary font-bold' 
                          : 'text-text hover:bg-neutral/5'
                      }`}
                    >
                      {mode.charAt(0).toUpperCase() + mode.slice(1)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {data && (
            <div className="text-sm text-text font-bold hidden xl:flex items-center bg-white/80 backdrop-blur-md px-5 h-11 rounded-full border border-neutral/20 shadow-lg pointer-events-auto shrink-0 whitespace-nowrap">
              Showing {page * pageSize + 1} - {Math.min((page + 1) * pageSize, data.total)} of {data.total}
            </div>
          )}
          
          {query.query ? (
            <div className="pointer-events-auto flex items-stretch bg-white/80 backdrop-blur-md border border-neutral/20 rounded-full shadow-lg h-11 shrink-0 relative">
              <div className="relative flex items-center h-full">
                <div className="py-0 pl-5 pr-9 text-primary font-bold text-sm h-full flex items-center w-[160px] rounded-l-full">
                  Relevance
                </div>
              </div>
              
              <div className="w-px bg-neutral/20 my-2"></div>
              
              <div className="px-4 text-primary flex items-center justify-center h-full rounded-r-full">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
                </svg>
              </div>
            </div>
          ) : (
            <div className="pointer-events-auto flex items-stretch bg-white/80 backdrop-blur-md border border-neutral/20 rounded-full shadow-lg h-11 shrink-0 relative dropdown-container">
              <div className="relative flex items-center h-full">
                <button 
                  onClick={() => setOpenDropdown(openDropdown === 'sort' ? null : 'sort')}
                  className="bg-transparent border-none text-text font-bold text-sm focus:ring-0 cursor-pointer py-0 pl-5 pr-9 outline-none hover:bg-neutral/5 transition-colors h-full flex items-center w-[160px] text-left rounded-l-full"
                >
                  {query.sort_by === 'rating' ? 'Rating' : 
                   query.sort_by === 'year' ? 'Year Published' :
                   query.sort_by === 'complexity' ? 'Complexity' :
                   query.sort_by === 'name' ? 'Name' : 'Rank'}
                </button>
                <div className="absolute right-3 flex items-center pointer-events-none text-secondary-text">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className={`w-4 h-4 transition-transform ${openDropdown === 'sort' ? 'rotate-180' : ''}`}><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>
                </div>
                
                {openDropdown === 'sort' && (
                  <div className="absolute top-[calc(100%+8px)] left-0 w-48 bg-white/95 backdrop-blur-md border border-neutral/20 rounded-2xl shadow-xl z-50 overflow-hidden text-sm flex flex-col ring-1 ring-black/5 p-1">
                    {[
                      { id: 'rank', label: 'Rank' },
                      { id: 'rating', label: 'Rating' },
                      { id: 'year', label: 'Year Published' },
                      { id: 'complexity', label: 'Complexity' },
                      { id: 'name', label: 'Name' }
                    ].map(opt => (
                      <button
                        key={opt.id}
                        onClick={() => {
                          handleFilterChange('sort_by', opt.id);
                          setOpenDropdown(null);
                        }}
                        className={`text-left px-4 py-2.5 rounded-xl font-medium transition-colors ${
                          (query.sort_by || 'rank') === opt.id 
                            ? 'bg-primary/10 text-primary font-bold' 
                            : 'text-text hover:bg-neutral/5'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              
              <div className="w-px bg-neutral/20 my-2"></div>
              
              <button 
                onClick={() => handleFilterChange('order', query.order === 'asc' ? 'desc' : 'asc')}
                className="px-4 text-primary hover:bg-neutral/5 transition-colors flex items-center justify-center h-full rounded-r-full"
                title={`Sort ${query.order === 'asc' ? 'Descending' : 'Ascending'}`}
              >
                {query.order === 'asc' ? (
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h9.75m4.5-4.5v12m0 0l-3.75-3.75M17.25 21L21 17.25" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h5.25m5.25-.75L17.25 9m0 0L21 12.75M17.25 9v12" />
                  </svg>
                )}
              </button>
            </div>
          )}
        </div>

        <header className="mb-8 flex flex-col lg:flex-row lg:items-end justify-between gap-6">
          <div className="flex items-center gap-4">
             <div>
               <h2 className="text-5xl sm:text-6xl font-serif text-text mb-2">All Games</h2>
               <p className="text-lg text-secondary-text">Browse and discover new board games.</p>
             </div>
          </div>
        </header>

        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
          </div>
        ) : isError ? (
          <div className="bg-red-50 text-red-600 p-4 rounded-lg border border-red-200">
            Error loading games. Make sure the backend is running and the database is seeded.
          </div>
        ) : data?.items.length === 0 ? (
          <div className="text-center py-24 text-secondary-text bg-surface rounded-3xl border border-neutral/20 shadow-sm flex flex-col items-center">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-16 h-16 mx-auto mb-4 text-neutral">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 15.75l-2.489-2.489m0 0a3.375 3.375 0 10-4.773-4.773 3.375 3.375 0 004.774 4.774zM21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-xl font-bold text-text mb-2">No games found</h3>
            <p>Try adjusting or clearing your filters.</p>
            <button onClick={clearFilters} className="mt-6 text-primary font-bold hover:underline">Clear Filters</button>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-6">
              {data?.items.map((item: any) => {
                const gameObj = item.game || item;
                return <GameCard key={gameObj.bgg_id} game={gameObj} />;
              })}
            </div>

            <div className="h-24"></div>

            <div className="fixed bottom-6 left-0 w-full px-4 z-40 flex justify-center pointer-events-none">
              <div className="bg-white/80 backdrop-blur-md px-6 shadow-lg border border-neutral/20 flex items-center justify-between gap-6 h-[4rem] rounded-full pointer-events-auto min-w-[300px]">
                <button
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page === 0}
                  className="flex items-center gap-1 text-primary font-bold hover:opacity-80 transition-opacity disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                    <path fillRule="evenodd" d="M7.72 12.53a.75.75 0 010-1.06l7.5-7.5a.75.75 0 111.06 1.06L9.31 12l6.97 6.97a.75.75 0 11-1.06 1.06l-7.5-7.5z" clipRule="evenodd" />
                  </svg>
                  <span>Prev</span>
                </button>
                
                <span className="text-text font-bold px-2">
                  Page {page + 1}
                </span>
                
                <button
                  onClick={() => handlePageChange(page + 1)}
                  disabled={data ? (page + 1) * pageSize >= data.total : false}
                  className="flex items-center gap-1 text-primary font-bold hover:opacity-80 transition-opacity disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <span>Next</span>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                    <path fillRule="evenodd" d="M16.28 11.47a.75.75 0 010 1.06l-7.5 7.5a.75.75 0 01-1.06-1.06L14.69 12 7.72 5.03a.75.75 0 011.06-1.06l7.5 7.5z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
