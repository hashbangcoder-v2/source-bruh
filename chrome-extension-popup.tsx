"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Search,
  ImageIcon,
  Cloud,
  Upload,
  ArrowLeft,
  Key,
  User,
  AlertCircle,
  CheckCircle,
  Settings,
} from "lucide-react"

type Screen = "landing" | "search" | "results" | "settings"

interface SearchResult {
  id: number
  imageUrl: string
  title: string
  source: string
}

export default function ChromeExtensionPopup() {
  const [currentScreen, setCurrentScreen] = useState<Screen>("landing")
  const [apiKey, setApiKey] = useState("")
  const [storedApiKey, setStoredApiKey] = useState("")
  const [query, setQuery] = useState("")
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [resultPage, setResultPage] = useState(1)
  const [activeLink, setActiveLink] = useState("https://photos.google.com/album/example-album-id")
  const [newLink, setNewLink] = useState("")

  // Mock user authentication status
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [userEmail, setUserEmail] = useState("user@gmail.com")

  // Mock API key validation
  const isApiKeyValid = storedApiKey.length > 0

  const handleApiKeySubmit = () => {
    if (apiKey.trim()) {
      setStoredApiKey(apiKey)
      setCurrentScreen("search")
    }
  }

  const handleSearch = () => {
    // Mock search results
    const mockResults: SearchResult[] = Array.from({ length: 9 }, (_, i) => ({
      id: i + 1,
      imageUrl: `/placeholder.svg?height=150&width=150&query=search result ${i + 1}`,
      title: `Result ${i + 1}`,
      source: i % 3 === 0 ? "Google Photos" : i % 3 === 1 ? "iCloud" : "Upload",
    }))

    setSearchResults(mockResults)
    setResultPage(1)
    setCurrentScreen("results")
  }

  const loadMoreResults = () => {
    const nextPage = resultPage + 1
    const newResults: SearchResult[] = Array.from({ length: 3 }, (_, i) => ({
      id: searchResults.length + i + 1,
      imageUrl: `/placeholder.svg?height=150&width=150&query=additional result ${i + 1}`,
      title: `Result ${searchResults.length + i + 1}`,
      source: i % 3 === 0 ? "Google Photos" : i % 3 === 1 ? "iCloud" : "Upload",
    }))

    setSearchResults([...searchResults, ...newResults])
    setResultPage(nextPage)
  }

  const scrambleApiKey = (key: string) => {
    if (key.length <= 8) return key
    return key.substring(0, 4) + "•".repeat(key.length - 8) + key.substring(key.length - 4)
  }

  // Landing Screen
  if (currentScreen === "landing") {
    return (
      <div className="w-96 p-6 bg-gradient-to-br from-blue-50 to-indigo-100 min-h-[300px]">
        <Card className="border-0 shadow-lg">
          <CardHeader className="text-center pb-4">
            <div className="mx-auto w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center mb-3">
              <Key className="h-6 w-6 text-white" />
            </div>
            <CardTitle className="text-xl font-semibold text-gray-800">Welcome</CardTitle>
            <p className="text-sm text-gray-600">Enter your API key to get started</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Input
                type="password"
                placeholder="Enter your Gemini API key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full"
              />
            </div>
            <Button
              onClick={handleApiKeySubmit}
              className="w-full bg-blue-600 hover:bg-blue-700"
              disabled={!apiKey.trim()}
            >
              Continue
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Search Screen
  if (currentScreen === "search") {
    return (
      <div className="w-96 p-4 bg-white shadow-lg">
        {/* Header with Settings */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Search</h2>
          <Button variant="ghost" size="sm" onClick={() => setCurrentScreen("settings")} className="p-1">
            <Settings className="h-4 w-4" />
          </Button>
        </div>

        {/* Status Bar */}
        <div className="mb-4 p-3 bg-gray-50 rounded-lg space-y-2">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2">
              <User className="h-3 w-3" />
              <span className="text-gray-600">User:</span>
              {isAuthenticated ? (
                <div className="flex items-center space-x-1">
                  <CheckCircle className="h-3 w-3 text-green-500" />
                  <span className="text-green-700">{userEmail}</span>
                </div>
              ) : (
                <div className="flex items-center space-x-1">
                  <AlertCircle className="h-3 w-3 text-red-500" />
                  <span className="text-red-600">Not authenticated</span>
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2">
              <Key className="h-3 w-3" />
              <span className="text-gray-600">API:</span>
              {isApiKeyValid ? (
                <div className="flex items-center space-x-1">
                  <CheckCircle className="h-3 w-3 text-green-500" />
                  <span className="text-green-700">Gemini ({scrambleApiKey(storedApiKey)})</span>
                </div>
              ) : (
                <div className="flex items-center space-x-1">
                  <AlertCircle className="h-3 w-3 text-red-500" />
                  <span className="text-red-600">Invalid/Inactive</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Search Input */}
        <div className="flex items-center space-x-2 mb-4">
          <Input
            type="text"
            placeholder="Enter your query"
            className="flex-grow"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button size="icon" onClick={handleSearch} disabled={!query.trim()}>
            <Search className="h-4 w-4" />
            <span className="sr-only">Search</span>
          </Button>
        </div>

        {/* Source Icons */}
        <div className="flex justify-center space-x-8">
          <Button variant="ghost" size="sm" className="flex flex-col items-center p-2">
            <ImageIcon className="h-6 w-6 mb-1 text-blue-600" />
            <span className="text-xs">Google Photos</span>
          </Button>
          <Button variant="ghost" size="sm" className="flex flex-col items-center p-2">
            <Cloud className="h-6 w-6 mb-1 text-gray-600" />
            <span className="text-xs">iCloud</span>
          </Button>
          <Button variant="ghost" size="sm" className="flex flex-col items-center p-2">
            <Upload className="h-6 w-6 mb-1 text-green-600" />
            <span className="text-xs">Upload</span>
          </Button>
        </div>
      </div>
    )
  }

  // Results Screen
  if (currentScreen === "results") {
    const currentResults = searchResults.slice(0, resultPage * 3)

    return (
      <div className="w-96 p-4 bg-white shadow-lg max-h-[500px] overflow-y-auto">
        {/* Header with Back Button */}
        <div className="flex items-center mb-4">
          <Button variant="ghost" size="sm" onClick={() => setCurrentScreen("search")} className="p-1 mr-2">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h2 className="text-lg font-semibold">Search Results</h2>
        </div>

        {/* Results Grid - 3 columns */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          {currentResults.map((result) => (
            <Card key={result.id} className="cursor-pointer hover:shadow-md transition-shadow">
              <CardContent className="p-2">
                <div className="flex flex-col items-center space-y-2">
                  <img
                    src={result.imageUrl || "/placeholder.svg"}
                    alt={result.title}
                    className="w-full h-20 object-cover rounded-lg"
                  />
                  <div className="text-center">
                    <h3 className="font-medium text-xs truncate w-full">{result.title}</h3>
                    <Badge variant="secondary" className="text-xs mt-1">
                      {result.source}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Load More Button */}
        {searchResults.length > currentResults.length && (
          <Button variant="outline" className="w-full bg-transparent" onClick={loadMoreResults}>
            Load More Results
          </Button>
        )}
      </div>
    )
  }

  // Settings Screen
  if (currentScreen === "settings") {
    return (
      <div className="w-96 p-4 bg-white shadow-lg">
        {/* Header with Back Button */}
        <div className="flex items-center mb-4">
          <Button variant="ghost" size="sm" onClick={() => setCurrentScreen("search")} className="p-1 mr-2">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h2 className="text-lg font-semibold">Settings</h2>
        </div>

        <div className="space-y-4">
          {/* Active Link Section */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Active Link</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-xs text-gray-600">Currently connected to:</div>
              <div className="p-2 bg-gray-50 rounded text-xs font-mono break-all">{activeLink}</div>
              <div className="space-y-2">
                <Input
                  type="text"
                  placeholder="Enter new Google Photos album link"
                  value={newLink}
                  onChange={(e) => setNewLink(e.target.value)}
                  className="text-xs"
                />
                <Button
                  size="sm"
                  className="w-full"
                  onClick={() => {
                    if (newLink.trim()) {
                      setActiveLink(newLink)
                      setNewLink("")
                    }
                  }}
                  disabled={!newLink.trim()}
                >
                  Update Link
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Account Section */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Account</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-xs text-gray-600">
                  {isAuthenticated ? `Logged in as ${userEmail}` : "Not logged in"}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setIsAuthenticated(false)
                    setCurrentScreen("search")
                  }}
                  disabled={!isAuthenticated}
                >
                  Log Out
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* API Key Section */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">API Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xs text-gray-600 mb-2">
                Current API Key: {isApiKeyValid ? scrambleApiKey(storedApiKey) : "Not set"}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="w-full bg-transparent"
                onClick={() => {
                  setStoredApiKey("")
                  setCurrentScreen("landing")
                }}
              >
                Reset API Key
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  return null
}
