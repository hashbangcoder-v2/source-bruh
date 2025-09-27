import React from "react";

/**
 * Landing (home) view that introduces the extension and routes to the query
 * experience once the user presses the “Get Started” button.
 */
// Correctly reference the icon from the public directory
const iconUrl = "/icons/icon.png";

function Landing({ onGetStarted }) {
  return (
    <div className="flex flex-col items-center text-center space-y-3">
      <img
        alt="Extension icon"
        className="mx-auto h-12 w-12"
        src={iconUrl}
      />
      <h1 className="mt-4 text-2xl font-bold">Source Bruh?</h1>
      <p className="text-sm text-gray-600">Easily search through your images!</p>
      <button onClick={onGetStarted} className="px-3 py-2 bg-black text-white rounded-md w-full">
        Get Started
      </button>
    </div>
  );
}

export default Landing;
