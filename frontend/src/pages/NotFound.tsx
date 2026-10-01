import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-3">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link to="/" className="text-sm text-indigo-600 hover:underline">
        Go back home
      </Link>
    </div>
  );
}