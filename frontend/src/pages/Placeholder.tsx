interface PlaceholderProps {
  title: string;
}

export default function Placeholder({ title }: PlaceholderProps) {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-gray-500">This page is coming soon.</p>
    </div>
  );
}