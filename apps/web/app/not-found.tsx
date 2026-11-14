import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-2xl font-semibold">Not found</h1>
      <p className="mt-2 text-muted">That season or race isn&apos;t in our data (2023 onward).</p>
      <Link href="/" className="mt-6 inline-block text-accent hover:underline">
        Back to the start
      </Link>
    </div>
  );
}
