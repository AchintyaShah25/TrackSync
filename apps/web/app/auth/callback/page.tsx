import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCallback } from "@/components/auth/AuthCallback";

export const metadata: Metadata = { title: "Signing in" };

export default function CallbackPage() {
  return (
    <Suspense>
      <AuthCallback />
    </Suspense>
  );
}
