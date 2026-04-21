"use client";

import { SignInButton, SignUpButton } from "@clerk/nextjs";
import { createElement, Fragment } from "react";

const signInClassName =
  "rounded-full border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-900 shadow-sm hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800";

const signUpClassName =
  "rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200";

/**
 * Clerk's SignInButton/SignUpButton use React.Children.only(). JSX whitespace between
 * the wrapper and &lt;button&gt; counts as extra text nodes — use createElement so
 * formatting tools cannot break runtime.
 */
export function AuthButtons() {
  return createElement(
    Fragment,
    null,
    createElement(
      SignInButton,
      { mode: "modal" },
      createElement(
        "button",
        { type: "button", className: signInClassName },
        "Sign in",
      ),
    ),
    createElement(
      SignUpButton,
      { mode: "modal" },
      createElement(
        "button",
        { type: "button", className: signUpClassName },
        "Sign up",
      ),
    ),
  );
}
