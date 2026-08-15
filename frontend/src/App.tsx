import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GamesList } from './pages/GamesList';
import { GameDetail } from './pages/GameDetail';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="sticky top-4 z-50 px-4 w-full">
          <header className="bg-white/80 backdrop-blur-md px-8 shadow-sm border border-neutral/20 flex items-center h-[4rem] rounded-full">
            <h1 className="text-4xl text-primary font-logo tracking-wide translate-y-5 pb-1">ludora</h1>
          </header>
        </div>
        <div className="min-h-screen bg-background">
          <Routes>
            <Route path="/" element={<Navigate to="/games" replace />} />
            <Route path="/games" element={<GamesList />} />
            <Route path="/games/:bgg_id" element={<GameDetail />} />
          </Routes>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
