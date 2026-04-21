import { Show, UserButton } from "@clerk/nextjs";
import Image from "next/image";
import Link from "next/link";

import { AuthButtons } from "@/components/auth-buttons";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex flex-1 w-full max-w-3xl flex-col items-center justify-between py-32 px-16 bg-white dark:bg-black sm:items-start">
        <div className="flex w-full items-center justify-between gap-4">
          <Image
            className="dark:invert"
            src="/next.svg"
            alt="Next.js logo"
            width={100}
            height={20}
            priority
          />
          <div className="flex items-center gap-3">
            <Show when="signed-out">
              <AuthButtons />
            </Show>
            <Show when="signed-in">
              <UserButton />
            </Show>
          </div>
        </div>

        <div className="flex flex-col items-center gap-6 text-center sm:items-start sm:text-left">
          <h1 className="max-w-xs text-3xl font-semibold leading-10 tracking-tight text-black dark:text-zinc-50">
            Smartpay
          </h1>
          <p className="max-w-md text-lg leading-8 text-zinc-600 dark:text-zinc-400">
            <Show when="signed-out">
              Use <strong>Sign in</strong> or <strong>Sign up</strong> above, or{" "}
              <Link
                href="/sign-in"
                className="font-medium text-zinc-950 underline dark:text-zinc-50"
              >
                open the sign-in page
              </Link>
              .
            </Show>
            <Show when="signed-in">
              You are signed in. Open the account menu on the right.
            </Show>
          </p>
        </div>
      </main>
    </div>
  );
}
