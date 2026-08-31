import { useCallback, useEffect, useRef, useState } from "react";
import {
  UnauthorizedError,
  checkSession,
  fetchResearchRun,
  fetchVenues,
  logout,
  setEditor as apiSetEditor,
  startResearch,
  updateVenue,
} from "./api";
import BandProfileSheet from "./BandProfileSheet";
import Board from "./Board";
import EditorPicker, { EDITOR_STORAGE_KEY } from "./EditorPicker";
import { useT } from "./i18n";
import Login from "./Login";
import ManualScan from "./ManualScan";
import ResearchDialog from "./ResearchDialog";
import Toast from "./Toast";
import VenueSheet from "./VenueSheet";
import { type ResearchRun, type Venue, type VenueStatus } from "./types";

type Session = "checking" | "anonymous" | "authenticated";
type View = "board" | "scan";

const RESEARCH_POLL_MS = 4000;
// Server-side runs are capped at ten minutes; stop polling well after that.
const RESEARCH_MAX_WAIT_MS = 12 * 60 * 1000;

type T = (key: string, vars?: Record<string, string | number>) => string;

function researchDoneText(run: ResearchRun, t: T): string {
  if (run.status === "failed") {
    return t("app.researchFailed");
  }
  let text;
  if (run.fields_filled > 0) {
    text =
      run.fields_filled === 1
        ? t("app.researchDoneOne")
        : t("app.researchDoneMany", { n: run.fields_filled });
  } else {
    text = t("app.researchDoneNothing");
  }
  // Finds that differ from what the card already says are kept aside for
  // manual checking — worth flagging right in the toast.
  const conflicts = run.findings.filter(
    (f) => !f.applied && f.old_value && f.old_value !== f.new_value,
  ).length;
  if (conflicts > 0) {
    text += t("app.researchConflicts", { n: conflicts });
  }
  return text;
}

export default function App() {
  const t = useT();
  const [session, setSession] = useState<Session>("checking");
  const [bandName, setBandName] = useState("");
  // The bandmate this device edits under; null until picked (or remembered).
  const [editor, setEditorState] = useState<string | null>(null);
  const [view, setView] = useState<View>("board");
  const [venues, setVenues] = useState<Venue[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Venue being edited, "new" for the add-venue form, null when the board is shown.
  const [active, setActive] = useState<Venue | "new" | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
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
      setError(err instanceof Error ? err.message : t("app.somethingWrong"));
    }
  }, [t]);

  const loadVenues = useCallback(async () => {
    try {
      setVenues(await fetchVenues());
      setError(null);
    } catch (err) {
      handleError(err);
    }
  }, [handleError]);

  // Open the dialog and, unless a run is already going, start a fresh one
  // researching the given venue (each card carries its own Search & fill).
  const openResearch = useCallback(async (venueId: number) => {
    setResearchOpen(true);
    if (researchRun?.status === "running") {
      return; // a run is in flight; just show it
    }
    setResearchError(null);
    setResearchRun(null);
    try {
      setResearchRun(await startResearch(venueId));
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
      showToast(researchDoneText(updated, t));
    };

    loop();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [researchRun?.id]);

  // Adopt a signed-in session: set the band, and reuse a remembered editor
  // name (silently, via the cookie) so returning users aren't asked again.
  const adoptSession = useCallback(
    async (s: { band_name: string; editor: string | null }) => {
      setBandName(s.band_name);
      let ed = s.editor;
      if (!ed) {
        let saved: string | null = null;
        try {
          saved = localStorage.getItem(EDITOR_STORAGE_KEY);
        } catch {
          saved = null;
        }
        if (saved) {
          try {
            await apiSetEditor(saved);
            ed = saved;
          } catch {
            ed = null;
          }
        }
      }
      setEditorState(ed);
      setSession("authenticated");
    },
    [],
  );

  useEffect(() => {
    checkSession()
      .then(adoptSession)
      .catch(() => setSession("anonymous"));
  }, [adoptSession]);

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
            .then(adoptSession)
            .catch(() => setSession("anonymous"))
        }
      />
    );
  }

  // Signed in but no bandmate chosen yet: ask who's editing before the board.
  if (!editor) {
    return (
      <EditorPicker bandName={bandName} onPicked={(name) => setEditorState(name)} />
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
        editor={editor}
        onChangeEditor={() => setEditorState(null)}
        onSignOut={async () => {
          await logout();
          setSession("anonymous");
          setBandName("");
          setEditorState(null);
          setVenues([]);
        }}
        onAddVenue={() => setActive("new")}
        onOpenScan={() => setView("scan")}
        onOpenProfile={() => setProfileOpen(true)}
        onOpenVenue={(venue) => setActive(venue)}
        onStatusChange={(venue: Venue, status: VenueStatus) => {
          // Optimistic: move the card immediately — a status change is tiny
          // and the free-tier backend can take seconds to answer. Roll back
          // (and say so) only if the save actually fails.
          const previousStatus = venue.status;
          setVenues((current) =>
            current.map((v) => (v.id === venue.id ? { ...v, status } : v)),
          );
          showToast(
            t("app.movedTo", {
              name: venue.name,
              status: t(`status.${status}`),
            }),
          );
          updateVenue(venue.id, { status }).catch((err) => {
            setVenues((current) =>
              current.map((v) =>
                v.id === venue.id ? { ...v, status: previousStatus } : v,
              ),
            );
            handleError(err);
          });
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
          onVenueChanged={loadVenues}
          onResearch={() => {
            const venue = active;
            setActive(null); // the research dialog takes over from the sheet
            if (venue && venue !== "new") {
              openResearch(venue.id);
            }
          }}
          onUnauthorized={() => setSession("anonymous")}
        />
      )}
      {profileOpen && (
        <BandProfileSheet
          onClose={() => setProfileOpen(false)}
          onUnauthorized={() => setSession("anonymous")}
        />
      )}
      {toast && (
        <Toast key={toast.id} message={toast.text} onDismiss={dismissToast} />
      )}
    </>
  );
}
