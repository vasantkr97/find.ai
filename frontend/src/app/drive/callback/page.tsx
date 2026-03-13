"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { notifyGoogleAuthComplete } from "@/lib/google-auth-popup";

export default function DriveCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    notifyGoogleAuthComplete();

    const closeTimer = window.setTimeout(() => {
      window.close();
    }, 250);

    const redirectTimer = window.setTimeout(() => {
      router.push("/");
    }, 1500);

    return () => {
      window.clearTimeout(closeTimer);
      window.clearTimeout(redirectTimer);
    };
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950">
      <div className="text-center space-y-4">
        <div className="w-16 h-16 mx-auto rounded-full bg-emerald-500/20 flex items-center justify-center">
          <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h1 className="text-xl font-semibold text-zinc-100">Google Drive Connected</h1>
        <p className="text-zinc-400">Finishing sign-in...</p>
      </div>
    </div>
  );
}
