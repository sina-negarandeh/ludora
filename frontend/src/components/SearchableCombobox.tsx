import React, { useState, useRef, useEffect } from 'react';

interface Props {
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
}

export const SearchableCombobox: React.FC<Props> = ({ options, selected, onChange, placeholder = "Search..." }) => {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredOptions = query === ''
    ? options
    : options.filter((option) => option.toLowerCase().includes(query.toLowerCase()));

  const removeOption = (optionToRemove: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(selected.filter(item => item !== optionToRemove));
  };

  const addOption = (optionToAdd: string) => {
    if (!selected.includes(optionToAdd)) {
      onChange([...selected, optionToAdd]);
    }
    setQuery('');
    // Keep focus on input for typing next
    inputRef.current?.focus();
  };

  return (
    <div className="relative" ref={wrapperRef}>
      <div 
        className={`w-full bg-neutral/10 border-none rounded-xl lg:rounded-2xl px-3 py-2 min-h-[44px] lg:min-h-[56px] text-left focus-within:ring-2 focus-within:ring-primary/50 transition-shadow flex flex-wrap items-center gap-2 cursor-text`}
        onClick={() => { setIsOpen(true); inputRef.current?.focus(); }}
      >
        {selected.map(item => (
          <span key={item} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-primary/10 text-primary text-xs lg:text-sm font-bold border border-primary/20">
            {item}
            <button
              type="button"
              onClick={(e) => removeOption(item, e)}
              className="hover:bg-primary/20 rounded-full p-0.5 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
              </svg>
            </button>
          </span>
        ))}
        
        <input
          ref={inputRef}
          type="text"
          className="flex-1 bg-transparent border-none p-0 focus:ring-0 text-text placeholder-secondary-text outline-none min-w-[80px] text-sm lg:text-base"
          placeholder={selected.length === 0 ? placeholder : ''}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
        />

        <div className="ml-auto pointer-events-none text-secondary-text pr-2">
           <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
             <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
           </svg>
        </div>
      </div>

      {isOpen && (
        <div className="absolute z-50 w-full mt-2 bg-white/95 backdrop-blur-xl border border-neutral/20 rounded-xl shadow-xl max-h-60 overflow-auto custom-scrollbar animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="p-1 flex flex-col">
            {filteredOptions.length === 0 ? (
              <div className="px-4 py-3 text-sm text-secondary-text">Nothing found.</div>
            ) : (
              filteredOptions.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => addOption(option)}
                  className="text-left px-4 py-2 text-sm text-text hover:bg-primary hover:text-white rounded-lg transition-colors flex items-center justify-between group"
                >
                  <span className="font-medium">{option}</span>
                  {selected.includes(option) && (
                    <svg className="w-4 h-4 text-primary group-hover:text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
