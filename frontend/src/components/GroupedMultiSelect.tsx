import React, { useState, useRef, useEffect } from 'react';

interface GroupedOption {
  group: string;
  values: { name: string; value: string }[];
}

interface Props {
  groups: GroupedOption[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
}

export const GroupedMultiSelect: React.FC<Props> = ({ groups, selected, onChange, placeholder = "Select..." }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeGroup, setActiveGroup] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setActiveGroup(null);
        setQuery('');
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectedByGroup = (group: string) =>
    groups.find(g => g.group === group)?.values.filter(v => selected.includes(v.name)).length || 0;

  const toggleValue = (name: string) => {
    if (selected.includes(name)) {
      onChange(selected.filter(item => item !== name));
    } else {
      onChange([...selected, name]);
    }
  };

  const filteredGroups = query === ''
    ? groups
    : groups.filter(g => g.group.toLowerCase().includes(query.toLowerCase()));

  const active = groups.find(g => g.group === activeGroup);
  const filteredValues = active
    ? (query === '' ? active.values : active.values.filter(v => v.value.toLowerCase().includes(query.toLowerCase())))
    : [];

  const openGroup = (group: string) => {
    setActiveGroup(group);
    setQuery('');
  };

  const goBack = () => {
    setActiveGroup(null);
    setQuery('');
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
        <div className="absolute z-50 w-full mt-2 bg-white/95 backdrop-blur-xl border border-neutral/20 rounded-xl shadow-xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
          {active ? (
            <div className="flex flex-col">
              <div className="flex items-center gap-2 p-2 border-b border-neutral/10">
                <button
                  type="button"
                  onClick={goBack}
                  className="p-1.5 rounded-lg hover:bg-neutral/10 text-secondary-text hover:text-text transition-colors flex-shrink-0"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                  </svg>
                </button>
                <span className="text-sm font-bold text-text truncate">{active.group}</span>
              </div>
              <div className="p-2 border-b border-neutral/10">
                <input
                  type="text"
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={`Search ${active.group}...`}
                  className="w-full bg-neutral/10 border-none rounded-lg px-3 py-2 text-sm text-text focus:ring-2 focus:ring-primary/50 outline-none"
                />
              </div>
              <div className="max-h-52 overflow-auto custom-scrollbar p-2 flex flex-col gap-1">
                {filteredValues.length === 0 ? (
                  <div className="px-3 py-2 text-sm text-secondary-text">Nothing found.</div>
                ) : (
                  filteredValues.map(v => {
                    const isSelected = selected.includes(v.name);
                    return (
                      <label key={v.name} className="flex items-center gap-3 px-3 py-2 hover:bg-neutral/10 rounded-lg cursor-pointer transition-colors">
                        <input
                          type="checkbox"
                          className="hidden"
                          checked={isSelected}
                          onChange={() => toggleValue(v.name)}
                        />
                        <div className={`w-5 h-5 flex-shrink-0 rounded flex items-center justify-center border transition-colors ${isSelected ? 'bg-primary border-primary' : 'border-neutral/30 bg-white'}`}>
                          {isSelected && (
                            <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                        <span className="text-sm text-text font-medium truncate">{v.value}</span>
                      </label>
                    );
                  })
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col">
              <div className="p-2 border-b border-neutral/10">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search groups..."
                  className="w-full bg-neutral/10 border-none rounded-lg px-3 py-2 text-sm text-text focus:ring-2 focus:ring-primary/50 outline-none"
                />
              </div>
              <div className="max-h-60 overflow-auto custom-scrollbar p-2 flex flex-col gap-1">
                {filteredGroups.length === 0 ? (
                  <div className="px-3 py-2 text-sm text-secondary-text">Nothing found.</div>
                ) : (
                  filteredGroups.map(g => {
                    const count = selectedByGroup(g.group);
                    return (
                      <button
                        key={g.group}
                        type="button"
                        onClick={() => openGroup(g.group)}
                        className="text-left px-3 py-2 text-sm text-text hover:bg-neutral/10 rounded-lg transition-colors flex items-center justify-between group"
                      >
                        <span className="font-medium flex items-center gap-2 truncate">
                          {g.group}
                          {count > 0 && (
                            <span className="px-1.5 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-bold flex-shrink-0">{count}</span>
                          )}
                        </span>
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 text-secondary-text flex-shrink-0">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                        </svg>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
