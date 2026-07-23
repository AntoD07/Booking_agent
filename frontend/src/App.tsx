import { useCallback, useEffect, useRef, useState } from "react";
import {
  UnauthorizedError,
  checkSession,
  fetchResearchRun,
  fetchVenues,
  logout,
  startResearch,
  updateVenue,
} from "./api";
import Board from "./Board";
import Login from "./Login";
import ManualScan from "./ManualScan";
import ResearchDialog from "./ResearchDialog";
import Toast from "./Toast";
import VenueSheet from "./VenueSheet";
import {
  STATUS_LABELS,
  type ResearchRun,
  type Venue,
  type VenueStatus,
} from "./types";

type Session = "checking" | "anonymous" | "authenticated";
type View = "board" | "scan";

const RESEARCH_POLL_MS = 4000;
// Server-side runs are capped at ten minutes; stop polling well after that.
const RESEARCH_MAX_WAIT_MS = 12 * 60 * 1000;

function researchDoneText(run: ResearchRun): string {
  if (run.status === "failed") {
    return "Search & fill couldn’t finish — open it for details";
  }
  if (run.fields_filled > 0) {
    const n = run.fields_filled;
    return `Search & fill done — ${n} field${n === 1 ? "" : "s"} filled`;
  }
  return "Search & fill done — nothing new to add";
}

export default function App() {
  const [session, setSession] = useState<Session>("checking");
  const [bandName, setBandName] = useState("");
  const [view, setView] = useState<View>("board");
  const [venues, setVenues] = useState<Venue[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Venue being edited, "new" for the add-venue form, null when the board is shown.
  const [active, setActive] = useState<Venue | "new" | null>(null);
  // The Search & fill dialog and the run it is following. Polling lives here,
  // not in the dialog, so a completed run still reaches the user (a toast)
  // even after they close the box while it is still working.
  const [researchOpen, setResearchOpen] = useState(false);
  const [researchRun, setResearchRun] = useState<ResearchRun | null>(null);
  const [researchError, setResearchError] = useState<string | null>(null);
  // Brief confirmations (status moves, research done). The moved card often
  // lands in an off-screen column, so the toast is the only sign it worked.
  const [toast, setToast] = useState<{ id: number; text: string } | null>(null);
  const toastId = useRef(0);
  const dismissToast = useCallback(() => setToast(null), []);
  const showToast = useCallback((text: string) => {
    setToast({ id: (toastId.current += 1), text });
  }, []);

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

  // Open the dialog and, unless a run is already going, start a fresh one.
  const openResearch = useCallback(async () => {
    setResearchOpen(true);
    if (researchRun?.status === "running") {
      return; // a run is in flight; just show it
    }
    setResearchError(null);
    setResearchRun(null);
    try {
      setResearchRun(await startResearch());
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setSession("anonymous");
      } else {
        setResearchError(
          err instanceof Error ? err.message : "Something went wrong",
        );
      }
    }
  }, [researchRun?.status]);

  // Follow the active run to completion, keyed on its id so a new run restarts
  // this. The recursive loop (not setInterval) avoids overlapping requests and
  // owns its own stop conditions.
  useEffect(() => {
    if (!researchRun || researchRun.status !== "running") {
      return;
    }
    const runId = researchRun.id;
    let cancelled = false;
    const startedAt = Date.now();

    const loop = async () => {
      await new Promise((resolve) => setTimeout(resolve, RESEARCH_POLL_MS));
      if (cancelled) return;
      let updated: ResearchRun;
      try {
        updated = await fetchResearchRun(runId);
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setSession("anonymous");
          return;
        }
        if (Date.now() - startedAt > RESEARCH_MAX_WAIT_MS) return;
        loop(); // transient failure — keep trying
        return;
      }
      if (cancelled) return;
      setResearchRun(updated);
      if (updated.status === "running") {
        if (Date.now() - startedAt > RESEARCH_MAX_WAIT_MS) {
          setResearchError(
            "The search is taking unusually long. Check back in a few minutes.",
          );
          return;
        }
        loop();
        return;
      }
      // Terminal: refresh the board if anything was written, and — crucially —
      // tell the user, whether or not the dialog is still open.
      if (updated.status === "completed" && updated.fields_filled > 0) {
        loadVenues();
      }
      showToast(researchDoneText(updated));
    };

    loop();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [researchRun?.id]);

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
        onOpenResearch={openResearch}
        onOpenVenue={(venue) => setActive(venue)}
        onStatusChange={async (venue: Venue, status: VenueStatus) => {
          try {
            await updateVenue(venue.id, { status });
            await loadVenues();
            showToast(`“${venue.name}” moved to ${STATUS_LABELS[status]}`);
          } catch (err) {
            handleError(err);
          }
        }}
      />
      {researchOpen && (
        <ResearchDialog
          run={researchRun}
          error={researchError}
          onClose={() => {
            setResearchOpen(false);
            // The run may still be writing venue fields in the background.
            loadVenues();
          }}
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
