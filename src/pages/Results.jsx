export default function Results({ results }) {
  if (!results?.length) {
    return <div className="text-sm text-gray-500">No results yet.</div>;
  }
  return (
    <div className="grid grid-cols-3 gap-2">
      {results.map((r) => (
        <div key={r.image_rowid} className="w-full h-20 bg-gray-100 rounded overflow-hidden">
          <img src={`http://127.0.0.1:5057${r.thumb_url}`} alt={r.description || "result"} className="w-full h-full object-cover" />
        </div>
      ))}
    </div>
  );
}


