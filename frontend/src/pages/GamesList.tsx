import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchGames } from '../api/games';
import { GameCard } from '../components/GameCard';

export const GamesList: React.FC = () => {
  const [page, setPage] = useState(0);
  const pageSize = 24;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['games', page],
    queryFn: () => fetchGames(page * pageSize, pageSize),
    staleTime: 60000,
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-5xl sm:text-6xl font-serif text-text mb-3">All Games</h2>
          <p className="text-lg sm:text-xl text-secondary-text">Browse and discover new board games.</p>
        </div>
        {data && (
          <div className="text-sm text-secondary-text font-medium">
            Showing {page * pageSize + 1} - {Math.min((page + 1) * pageSize, data.total)} of {data.total} games
          </div>
        )}
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
        <div className="text-center py-12 text-secondary-text">
          No games found. Did you run the ingestion script?
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {data?.items.map((game) => (
              <GameCard key={game.bgg_id} game={game} />
            ))}
          </div>

          {/* Add a bottom padding spacer so the last row of games isn't hidden behind the floating bar */}
          <div className="h-24"></div>

          <div className="fixed bottom-6 left-0 w-full px-4 z-50 flex justify-center pointer-events-none">
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
  );
};
