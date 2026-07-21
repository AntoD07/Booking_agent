import { useCallback, useEffect, useState } from "react";
import { UnauthorizedError, checkSession, fetchVenues, logout } from "./api";
import Board from "./Board";
import Login from "./Login";
import type { Venue } from "./types";

type Session = "checking" | "anonymous" | "authenticated";

export default function App() {
  const [session, setSession] = useState<Session>("checking");
  const [venues, setVenues] = useState<Venue[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadVenues = useCallback(async () => {
    try {
      setVenues(await fetchVenues());
      setError(null);
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setSession("anonymous");
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong");
      }
    }
  }, []);

  useEffect(() => {
    checkSession()
      .then(() => setSession("authenticated"))
      .catch(() => setSession("anonymous"));
  }, []);

  useEffect(() => {
    if (session === "authenticated") {
      loadVenues();
    }
  }, [session, loadVenues]);

  if (session === "checking") {
    return null;
  }

  if (session === "anonymous") {
    return <Login onSuccess={() => setSession("authenticated")} />;
  }

  return (
    <Board
      venues={venues}
      error={error}
      onSignOut={async () => {
        await logout();
        setSession("anonymous");
        setVenues([]);
      }}
    />
  );
}
