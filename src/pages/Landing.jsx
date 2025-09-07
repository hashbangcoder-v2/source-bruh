import iconUrl from "../icons/icon.png";

export default function Landing({ onGetStarted }) {
  return (
    <div className="flex flex-col items-center text-center space-y-3">
      <img src={iconUrl} alt="App icon" className="w-16 h-16 rounded" />
      <p className="text-sm text-gray-600">Easily search through your images!</p>
      <button onClick={onGetStarted} className="px-3 py-2 bg-black text-white rounded-md w-full">
        Get Started
      </button>
    </div>
  );
}


