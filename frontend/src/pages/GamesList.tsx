import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchGames, fetchCategories, fetchMechanics } from '../api/games';
import type { GameFilters } from '../api/games';
import { GameCard } from '../components/GameCard';

export const GamesList: React.FC = () => {
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState('rank');
  const [order, setOrder] = useState('asc');
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  
  const [filters, setFilters] = useState<GameFilters>({});
  
  const pageSize = 24;

  const { data: categories } = useQuery({ queryKey: ['categories'], queryFn: fetchCategories, staleTime: Infinity });
  const { data: mechanics } = useQuery({ queryKey: ['mechanics'], queryFn: fetchMechanics, staleTime: Infinity });

  const { data, isLoading, isError } = useQuery({
    queryKey: ['games', page, sortBy, order, filters],
    queryFn: () => fetchGames(page * pageSize, pageSize, sortBy, order, filters),
    staleTime: 60000,
  });

  React.useEffect(() => {
    setPage(0);
  }, [sortBy, order, filters]);

  const handleFilterChange = (key: keyof GameFilters, value: any) => {
    setFilters(prev => {
      const newFilters = { ...prev };
      if (value === '' || value === undefined || (typeof value === 'number' && isNaN(value))) {
        delete newFilters[key];
      } else {
        newFilters[key] = value;
      }
      return newFilters;
    });
  };

  const clearFilters = () => setFilters({});

  return (
    <div className="w-full px-4 py-8 flex gap-6 lg:gap-8 items-start relative">
      
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
        </button>
      )}

      {/* Desktop Sidebar Container */}
      <div className={`hidden lg:block sticky top-24 z-10 transition-all duration-300 flex-shrink-0 ${isSidebarOpen ? 'w-[280px]' : 'w-[140px]'}`}>
        {isSidebarOpen ? (
          <aside className="w-full bg-white/80 backdrop-blur-xl border border-neutral/20 shadow-sm rounded-3xl p-6 flex flex-col h-[calc(100vh-8rem)] animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-serif text-text font-bold">Filters</h3>
              <button onClick={() => setSidebarOpen(false)} className="p-1.5 rounded-full hover:bg-neutral/10 text-secondary-text hover:text-text transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 space-y-6 custom-scrollbar">
              
              {/* Search */}
              <div>
                <label className="block text-sm font-bold text-secondary-text mb-2">Search</label>
                <input 
                  type="text" 
                  placeholder="e.g. Gloomhaven..."
                  value={filters.query || ''}
                  onChange={(e) => handleFilterChange('query', e.target.value)}
                  className="w-full bg-neutral/10 border-none rounded-xl px-4 py-2.5 text-text focus:ring-2 focus:ring-primary/50 placeholder-secondary-text/50 outline-none transition-shadow"
                />
              </div>

              {/* Category */}
              <div>
                <label className="block text-sm font-bold text-secondary-text mb-2">Category</label>
                <select 
                  value={filters.category || ''}
                  onChange={(e) => handleFilterChange('category', e.target.value)}
                  className="w-full bg-neutral/10 border-none rounded-xl px-4 py-2.5 text-text focus:ring-2 focus:ring-primary/50 outline-none appearance-none cursor-pointer"
                >
                  <option value="">All Categories</option>
                  {categories?.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              {/* Mechanic */}
              <div>
                <label className="block text-sm font-bold text-secondary-text mb-2">Mechanic</label>
                <select 
                  value={filters.mechanic || ''}
                  onChange={(e) => handleFilterChange('mechanic', e.target.value)}
                  className="w-full bg-neutral/10 border-none rounded-xl px-4 py-2.5 text-text focus:ring-2 focus:ring-primary/50 outline-none appearance-none cursor-pointer"
                >
                  <option value="">All Mechanics</option>
                  {mechanics?.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>

              {/* Players */}
              <div>
                 <label className="block text-sm font-bold text-secondary-text mb-2">Players</label>
                 <div className="flex items-center gap-2">
                   <input type="number" min="1" placeholder="Min" value={filters.min_players || ''} onChange={(e) => handleFilterChange('min_players', parseInt(e.target.value))} className="w-full bg-neutral/10 border-none rounded-xl px-3 py-2 text-text focus:ring-2 focus:ring-primary/50 outline-none" />
                   <span className="text-secondary-text">-</span>
                   <input type="number" min="1" placeholder="Max" value={filters.max_players || ''} onChange={(e) => handleFilterChange('max_players', parseInt(e.target.value))} className="w-full bg-neutral/10 border-none rounded-xl px-3 py-2 text-text focus:ring-2 focus:ring-primary/50 outline-none" />
                 </div>
              </div>

              {/* Complexity */}
              <div>
                 <label className="block text-sm font-bold text-secondary-text mb-2">Complexity (1.0 - 5.0)</label>
                 <div className="flex items-center gap-2">
                   <input type="number" step="0.1" min="1" max="5" placeholder="Min" value={filters.min_weight || ''} onChange={(e) => handleFilterChange('min_weight', parseFloat(e.target.value))} className="w-full bg-neutral/10 border-none rounded-xl px-3 py-2 text-text focus:ring-2 focus:ring-primary/50 outline-none" />
                   <span className="text-secondary-text">-</span>
                   <input type="number" step="0.1" min="1" max="5" placeholder="Max" value={filters.max_weight || ''} onChange={(e) => handleFilterChange('max_weight', parseFloat(e.target.value))} className="w-full bg-neutral/10 border-none rounded-xl px-3 py-2 text-text focus:ring-2 focus:ring-primary/50 outline-none" />
                 </div>
              </div>

            </div>

            <div className="pt-6 border-t border-neutral/20 mt-4">
               <button onClick={clearFilters} className="w-full py-3 rounded-xl bg-neutral/20 text-text font-bold hover:bg-neutral/30 transition-colors">
                  Clear All Filters
               </button>
            </div>
          </aside>
        ) : (
          <button 
            onClick={() => setSidebarOpen(true)}
            className="w-full bg-white/80 backdrop-blur-md shadow-sm border border-neutral/20 flex items-center justify-center gap-2 h-[4rem] rounded-full text-primary font-bold hover:opacity-80 transition-opacity animate-in fade-in zoom-in-95 duration-200"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
            </svg>
            <span>Filters</span>
          </button>
        )}
      </div>

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
              {/* Search */}
              <div>
                <label className="block text-lg font-bold text-secondary-text mb-3">Search</label>
                <input 
                  type="text" 
                  placeholder="e.g. Gloomhaven..."
                  value={filters.query || ''}
                  onChange={(e) => handleFilterChange('query', e.target.value)}
                  className="w-full bg-neutral/10 border-none rounded-2xl px-6 py-4 text-lg text-text outline-none"
                />
              </div>

              {/* Category */}
              <div>
                <label className="block text-lg font-bold text-secondary-text mb-3">Category</label>
                <select 
                  value={filters.category || ''}
                  onChange={(e) => handleFilterChange('category', e.target.value)}
                  className="w-full bg-neutral/10 border-none rounded-2xl px-6 py-4 text-lg text-text outline-none appearance-none"
                >
                  <option value="">All Categories</option>
                  {categories?.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              {/* Mechanic */}
              <div>
                <label className="block text-lg font-bold text-secondary-text mb-3">Mechanic</label>
                <select 
                  value={filters.mechanic || ''}
                  onChange={(e) => handleFilterChange('mechanic', e.target.value)}
                  className="w-full bg-neutral/10 border-none rounded-2xl px-6 py-4 text-lg text-text outline-none appearance-none"
                >
                  <option value="">All Mechanics</option>
                  {mechanics?.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
          </div>
          
          <div className="pt-8 mt-8 border-t border-neutral/20">
            <button onClick={() => { clearFilters(); setSidebarOpen(false); }} className="w-full py-4 rounded-2xl bg-primary text-white font-bold text-lg">
              Show Results
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 min-w-0 transition-all duration-300">
        <header className="mb-8 flex flex-col lg:flex-row lg:items-end justify-between gap-6">
          <div className="flex items-center gap-4">
             <div>
               <h2 className="text-5xl sm:text-6xl font-serif text-text mb-2">All Games</h2>
               <p className="text-lg text-secondary-text">Browse and discover new board games.</p>
             </div>
          </div>
          
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            {data && (
              <div className="text-sm text-secondary-text font-medium hidden xl:block mr-2">
                Showing {page * pageSize + 1} - {Math.min((page + 1) * pageSize, data.total)} of {data.total}
              </div>
            )}
            
            <div className="flex items-center gap-2 bg-surface border border-neutral/30 rounded-xl p-1 shadow-sm">
              <select 
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="bg-transparent border-none text-text font-medium text-sm focus:ring-0 cursor-pointer py-1.5 pl-3 pr-8 appearance-none outline-none"
              >
                <option value="rank">Rank</option>
                <option value="rating">Rating</option>
                <option value="year">Year Published</option>
                <option value="complexity">Complexity</option>
                <option value="name">Name</option>
              </select>
              
              <button 
                onClick={() => setOrder(order === 'asc' ? 'desc' : 'asc')}
                className="p-1.5 bg-neutral/10 hover:bg-neutral/20 rounded-lg text-secondary-text transition-colors"
                title={`Sort ${order === 'asc' ? 'Descending' : 'Ascending'}`}
              >
                {order === 'asc' ? (
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h9.75m4.5-4.5v12m0 0l-3.75-3.75M17.25 21L21 17.25" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h5.25m5.25-.75L17.25 9m0 0L21 12.75M17.25 9v12" />
                  </svg>
                )}
              </button>
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
              {data?.items.map((game) => (
                <GameCard key={game.bgg_id} game={game} />
              ))}
            </div>

            <div className="h-24"></div>

            <div className="fixed bottom-6 left-0 w-full px-4 z-40 flex justify-center pointer-events-none">
              <div className="bg-white/80 backdrop-blur-md px-6 shadow-lg border border-neutral/20 flex items-center justify-between gap-6 h-[4rem] rounded-full pointer-events-auto min-w-[300px]">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
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
                  onClick={() => setPage((p) => p + 1)}
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
