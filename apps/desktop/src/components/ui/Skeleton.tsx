import React from 'react';

interface SkeletonProps {
  className?: string;
}

/** Shimmering placeholder block for loading states. */
export const Skeleton: React.FC<SkeletonProps> = ({ className = '' }) => (
  <div className={`skeleton ${className}`} aria-hidden="true" />
);

/** A card-shaped skeleton matching the project card layout. */
export const CardSkeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div
    className={`rounded-2xl border border-matte-border bg-matte-card/40 p-6 space-y-4 ${className}`}
    aria-busy="true"
    aria-label="Loading"
  >
    <div className="flex items-center gap-2.5">
      <Skeleton className="w-9 h-9 rounded-lg" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3 w-1/2" />
        <Skeleton className="h-2 w-1/3" />
      </div>
    </div>
    <div className="flex gap-1.5">
      <Skeleton className="h-4 w-12 rounded-full" />
      <Skeleton className="h-4 w-16 rounded-full" />
    </div>
    <div className="grid grid-cols-2 gap-3">
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-full" />
    </div>
  </div>
);
