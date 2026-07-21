import { useCallback, useEffect, useState } from "react";
import {
  UnauthorizedError,
  checkSession,
  fetchVenues,
  logout,
  updateVenue,
} from "./api";
import Board from "./Board";
import Login from "./Login";
import VenueSheet from "./VenueSheet";
import type { Venue, VenueStatus } from "./types";

type Session = "checking" | "anonymous" | "authenticated";

export default function App() {
  const [session, setSession] = useState<Session>("checking");
  const [venues, setVenues] = useState<Venue[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Venue being edited, "new" for the add-venue form, null when the board is shown.
  const [active, setActive] = useState<Venue | "new" | null>(null);

  const handleError = useCallback((err: unknown) => {
    if (err instanceof UnauthorizedError) {
      setSession("anonymous");
    } else {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }, []);

  const loadVenues = useCallback(async () => {
    try {
      setVenues(await fetchVenues());
      setError(null);
    } catch (err) {
      handleError(err);
    }
  }, [handleError]);

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
    <>
      <Board
        venues={venues}
        error={error}
        onSignOut={async () => {
          await logout();
          setSession("anonymous");
          setVenues([]);
        }}
        onAddVenue={() => setActive("new")}
        onOpenVenue={(venue) => setActive(venue)}
        onStatusChange={async (venue: Venue, status: VenueStatus) => {
          try {
            await updateVenue(venue.id, { status });
            await loadVenues();
          } catch (err) {
            handleError(err);
          }
        }}
      />
      {active !== null && (
        <VenueSheet
          venue={active === "new" ? null : active}
          onClose={() => setActive(null)}
          onSaved={() => {
            setActive(null);
            loadVenues();
          }}
        />
      )}
    </>
  );
}
