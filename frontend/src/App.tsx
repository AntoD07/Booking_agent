import { useCallback, useEffect, useRef, useState } from "react";
import {
  UnauthorizedError,
  checkSession,
  fetchVenues,
  logout,
  updateVenue,
} from "./api";
import Board from "./Board";
import Login from "./Login";
import ManualScan from "./ManualScan";
import ResearchDialog from "./ResearchDialog";
import Toast from "./Toast";
import VenueSheet from "./VenueSheet";
import { STATUS_LABELS, type Venue, type VenueStatus } from "./types";

type Session = "checking" | "anonymous" | "authenticated";
type View = "board" | "scan";

export default function App() {
  const [session, setSession] = useState<Session>("checking");
  const [bandName, setBandName] = useState("");
  const [view, setView] = useState<View>("board");
  const [venues, setVenues] = useState<Venue[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Venue being edited, "new" for the add-venue form, null when the board is shown.
  const [active, setActive] = useState<Venue | "new" | null>(null);
  // The Search & fill dialog: starts a research run when opened.
  const [researching, setResearching] = useState(false);
  // Brief confirmation after a status change — the moved card often lands in
  // an off-screen column, so the toast is the only sign it worked.
  const [toast, setToast] = useState<{ id: number; text: string } | null>(null);
  const toastId = useRef(0);
  const dismissToast = useCallback(() => setToast(null), []);

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
      .then((session) => {
        setBandName(session.band_name);
        setSession("authenticated");
      })
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
    return (
      <Login
        onSuccess={() =>
          checkSession()
            .then((s) => {
              setBandName(s.band_name);
              setSession("authenticated");
            })
            .catch(() => setSession("anonymous"))
        }
      />
    );
  }

  if (view === "scan") {
    return (
      <ManualScan
        onBack={() => {
          setView("board");
          // Accepted suggestions became venues while we were away.
          loadVenues();
        }}
        onUnauthorized={() => setSession("anonymous")}
      />
    );
  }

  return (
    <>
      <Board
        venues={venues}
        error={error}
        bandName={bandName}
        onSignOut={async () => {
          await logout();
          setSession("anonymous");
          setBandName("");
          setVenues([]);
        }}
        onAddVenue={() => setActive("new")}
        onOpenScan={() => setView("scan")}
        onOpenResearch={() => setResearching(true)}
        onOpenVenue={(venue) => setActive(venue)}
        onStatusChange={async (venue: Venue, status: VenueStatus) => {
          try {
            await updateVenue(venue.id, { status });
            await loadVenues();
            setToast({
              id: (toastId.current += 1),
              text: `“${venue.name}” moved to ${STATUS_LABELS[status]}`,
            });
          } catch (err) {
            handleError(err);
          }
        }}
      />
      {researching && (
        <ResearchDialog
          onClose={() => {
            setResearching(false);
            // The run may still be writing venue fields in the background.
            loadVenues();
          }}
          onUnauthorized={() => setSession("anonymous")}
          onVenuesChanged={loadVenues}
        />
      )}
      {active !== null && (
        <VenueSheet
          venue={active === "new" ? null : active}
          onClose={() => {
            setActive(null);
            // Artist appearances save immediately inside the sheet, so the
            // board list may be stale even when the form itself wasn't saved.
            loadVenues();
          }}
          onSaved={() => {
            setActive(null);
            loadVenues();
          }}
        />
      )}
      {toast && (
        <Toast key={toast.id} message={toast.text} onDismiss={dismissToast} />
      )}
    </>
  );
}
