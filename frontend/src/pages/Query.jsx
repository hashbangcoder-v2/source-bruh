import { Search } from "lucide-react";

export default function Query({ query, setQuery, onSearch, loading }) {
  return (
    <div className="space-y-3">
      <div className="flex space-x-2">
        <input
          type="text"
          placeholder="Describe the chart, infographic, or topic"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-grow p-2 border border-gray-300 rounded-md"
        />
        <button className="p-2 bg-black text-white rounded-md" onClick={onSearch} disabled={loading}>
          <Search className="h-4 w-4" />
        </button>
      </div>
      <p className="text-xs text-gray-500">Tip: Try “GDP bar chart 2010-2020” or “infographic safety signs”.</p>
    </div>
  );
}
