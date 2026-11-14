import { Skeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-8 w-64" label="Loading page" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <Skeleton className="mt-4 h-72" />
    </div>
  );
}
