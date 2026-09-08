// This module must never be bundled for the browser.
//
// `server-only` turns an accidental client import into a build-time error
// instead of a silent credential leak. That is not theoretical here: the
// previous version of this app was a "use client" page that imported this
// module directly, so the Supabase key was inlined into a JavaScript chunk
// served to every visitor.
import "server-only";

import { createClient } from "@supabase/supabase-js";

// Deliberately NOT prefixed NEXT_PUBLIC_. Next.js inlines any NEXT_PUBLIC_*
// value it sees referenced from client-bundled code, so the prefix itself is
// the hazard. Without it, the value cannot reach the browser even by accident.
const url = process.env.SUPABASE_URL;
const key = process.env.SUPABASE_KEY;

if (!url || !key) {
  throw new Error(
    "Missing SUPABASE_URL / SUPABASE_KEY. Set them in web/.env.local (server-side, " +
      "no NEXT_PUBLIC_ prefix) and in the hosting provider's environment settings.",
  );
}

export const supabase = createClient(url, key, {
  auth: { persistSession: false },
  global: {
    // Opt every PostgREST call out of Next's fetch cache, so page-level
    // `revalidate` is the single place freshness is decided. Otherwise each
    // query caches on its own schedule and the page can mix a fresh prediction
    // with a stale one from the previous render.
    fetch: (input, init) => fetch(input, { ...init, cache: "no-store" }),
  },
});
