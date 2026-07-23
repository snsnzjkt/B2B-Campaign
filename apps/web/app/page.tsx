import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 bg-neutral-50 px-4 text-center">
      <h1 className="text-3xl font-semibold text-neutral-900">B2B Campaign</h1>
      <div className="flex gap-3">
        <Link href="/login" className={cn(buttonVariants({ variant: "outline" }))}>
          Log in
        </Link>
        <Link href="/register" className={cn(buttonVariants())}>
          Register
        </Link>
      </div>
    </main>
  );
}
