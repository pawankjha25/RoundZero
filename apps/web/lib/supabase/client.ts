// Browser Supabase client - Client Components only (login page, anywhere that
// needs supabase.auth.* directly). Standard @supabase/ssr pattern for Next.js
// App Router. See apps/web/lib/supabase/server.ts for the Server
// Component/Route Handler counterpart and middleware.ts for session refresh.
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
