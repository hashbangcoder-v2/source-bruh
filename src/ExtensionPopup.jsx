import { Search, Image, Cloud, Upload } from "lucide-react";
import { useState } from "react";

export default function ExtensionPopup() {
  const [query, setQuery] = useState("");

  return (
    <div className="w-80 p-4 bg-white shadow-lg rounded-lg">
      <div className="flex flex-col space-y-4">
        {/* Search Bar */}
        <div className="flex space-x-2">
          <input
            type="text"
            placeholder="Enter your query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-grow p-2 border border-gray-300 rounded-md"
          />
          <button className="p-2 bg-black text-white rounded-md" aria-label="Search">
            <Search className="h-4 w-4" />
          </button>
        </div>
        {/* Icons Row */}
        <div className="flex justify-center space-x-6">
          <button
            className="hover:bg-gray-100 p-2 rounded-full"
            aria-label="Google Photos"
          >
            <Image className="h-6 w-6 text-blue-500" />
          </button>
          <button
            className="hover:bg-gray-100 p-2 rounded-full"
            aria-label="iCloud"
          >
            <Cloud className="h-6 w-6 text-gray-500" />
          </button>
          <button
            className="hover:bg-gray-100 p-2 rounded-full"
            aria-label="Upload"
          >
            <Upload className="h-6 w-6 text-green-500" />
          </button>
        </div>
      </div>
    </div>
  );
}
