import React, { useState, useRef, useEffect } from 'react';
import { useChatMutation } from '../api/assistant';
import { AssistantMessageBubble } from './AssistantMessageBubble';
import { ChatBubbleLeftRightIcon, XMarkIcon, PaperAirplaneIcon, SparklesIcon } from '@heroicons/react/24/solid';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  responseType?: string;
  data?: any;
};

export const AssistantDrawer: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Hi! I am the Ludora assistant. You can ask me to find, compare, or recommend board games.',
    }
  ]);
  const [input, setInput] = useState('');
  
  const chatMutation = useChatMutation();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) scrollToBottom();
  }, [messages, isOpen, chatMutation.isPending]);

  const handleSend = async (text: string) => {
    if (!text.trim()) return;
    
    const userMsg: Message = { id: Date.now().toString(), role: 'user', text };
    setMessages(prev => [...prev, userMsg]);
    setInput('');

    try {
      // In the future, pass conversation_id here
      const res = await chatMutation.mutateAsync({ message: text });
      
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: res.message,
        responseType: res.type,
        data: res.data,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: 'Sorry, I encountered an error communicating with the server.',
        responseType: 'error'
      }]);
    }
  };

  return (
    <>
      {/* Floating Action Button */}
      <button
        onClick={() => setIsOpen(true)}
        className={`fixed bottom-6 right-6 w-14 h-14 bg-white/80 backdrop-blur-md border border-neutral/20 text-primary rounded-full shadow-lg flex items-center justify-center hover:bg-neutral/5 hover:scale-105 transition-all z-40 ${isOpen ? 'hidden' : ''}`}
        aria-label="Open Assistant"
      >
        <ChatBubbleLeftRightIcon className="w-7 h-7" />
      </button>

      {/* Drawer Overlay (Mobile) */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-50 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Drawer Panel */}
      <div 
        className={`fixed z-50 flex flex-col transition-all duration-300 ease-in-out transform shadow-2xl overflow-hidden
          md:top-24 md:right-6 md:h-[calc(100vh-7.5rem)] md:w-[400px] md:rounded-3xl md:border md:bg-white/80 md:backdrop-blur-xl
          top-0 right-0 w-full h-[100dvh] bg-background border-l border-neutral/20
          ${isOpen ? 'opacity-100 translate-x-0 pointer-events-auto' : 'opacity-0 md:translate-x-8 translate-x-full pointer-events-none'}`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-neutral/20 bg-transparent shrink-0">
          <div className="flex flex-col">
            <h2 className="text-xl font-serif text-text font-bold">Assistant</h2>
            <div className="flex items-center gap-1 text-xs text-secondary-text font-sans">
              <SparklesIcon className="w-3 h-3 text-primary" />
              <span>Powered by Qwen</span>
            </div>
          </div>
          <button 
            onClick={() => setIsOpen(false)}
            className="p-1.5 rounded-full hover:bg-neutral/10 text-secondary-text hover:text-text transition-colors"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Message List */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
          {messages.map(msg => (
            <div key={msg.id} className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'user' ? (
                <div className="bg-primary text-white px-4 py-2.5 rounded-2xl rounded-tr-sm max-w-[85%] text-sm shadow-sm">
                  {msg.text}
                </div>
              ) : (
                <AssistantMessageBubble 
                  message={msg.text} 
                  responseType={msg.responseType} 
                  data={msg.data}
                  onSelectOption={(option) => handleSend(option)}
                />
              )}
            </div>
          ))}
          
          {chatMutation.isPending && (
            <div className="flex w-full justify-start">
              <div className="bg-white/80 backdrop-blur-md border border-neutral/20 px-5 py-3 rounded-2xl rounded-tl-sm shadow-sm flex items-center gap-2">
                <span className="w-2 h-2 bg-primary/40 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-primary/80 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} className="h-2 shrink-0" />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-transparent border-t border-neutral/20 shrink-0">
          <form 
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(input);
            }}
            className="relative flex items-center"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask me anything..."
              className="w-full bg-white/80 backdrop-blur-sm border border-neutral/20 shadow-sm rounded-full py-3 pl-5 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
              disabled={chatMutation.isPending}
            />
            <button
              type="submit"
              disabled={!input.trim() || chatMutation.isPending}
              className="absolute right-1.5 p-2 bg-primary text-white rounded-full disabled:opacity-50 disabled:bg-neutral/40 transition-colors shadow-sm"
            >
              <PaperAirplaneIcon className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </>
  );
};
