import React, { useState, useRef, useEffect } from 'react';

interface Props {
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
}

export const MultiSelectDropdown: React.FC<Props> = ({ options, selected, onChange, placeholder = "Select..." }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleOption = (option: string) => {
    if (selected.includes(option)) {
      onChange(selected.filter(item => item !== option));
    } else {
      onChange([...selected, option]);
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full bg-neutral/10 border-none rounded-xl lg:rounded-2xl px-4 lg:px-6 py-2.5 lg:py-4 pr-10 text-left text-text focus:ring-2 focus:ring-primary/50 outline-none transition-shadow flex items-center justify-between"
      >
        <span className={`block truncate ${selected.length === 0 ? 'text-secondary-text' : ''}`}>
          {selected.length === 0 ? placeholder : `${selected.length} Selected`}
        </span>
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute z-50 w-full mt-2 bg-white/95 backdrop-blur-xl border border-neutral/20 rounded-xl shadow-xl max-h-60 overflow-auto custom-scrollbar animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="p-2 flex flex-col gap-1">
            {options.map(option => {
              const isSelected = selected.includes(option);
              return (
                <label key={option} className="flex items-center gap-3 px-3 py-2 hover:bg-neutral/10 rounded-lg cursor-pointer transition-colors">
                  <input 
                    type="checkbox" 
                    className="hidden" 
                    checked={isSelected} 
                    onChange={() => toggleOption(option)} 
                  />
                  <div className={`w-5 h-5 flex-shrink-0 rounded flex items-center justify-center border transition-colors ${isSelected ? 'bg-primary border-primary' : 'border-neutral/30 bg-white'}`}>
                    {isSelected && (
                      <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>
                  <span className="text-sm text-text font-medium">{option}</span>
                </label>
              );
            })}
            {options.length === 0 && <div className="px-3 py-2 text-sm text-secondary-text">No options available</div>}
          </div>
        </div>
      )}
    </div>
  );
};
