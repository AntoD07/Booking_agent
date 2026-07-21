import { useEffect, useState } from "react";
import {
  UnauthorizedError,
  acceptSuggestion,
  discoverVenues,
  fetchArtists,
} from "./api";
import { TYPE_LABELS, type Artist, type Suggestion } from "./types";
import "./Scouting.css";

type ReviewState = "pending" | "accepting" | "accepted" | "dismissed";

interface ScoutingProps {
  onBack: () => void;
  onUnauthorized: () => void;
}

export default function Scouting({ onBack, onUnauthorized }: ScoutingProps) {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [firstArtist, setFirstArtist] = useState("");
  const [secondArtist, setSecondArtist] = useState("");
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [review, setReview] = useState<ReviewState[]>([]);

  useEffect(() => {
    fetchArtists()
      .then(setArtists)
      .catch(() => {
        // The datalist is a convenience; free text still works without it.
      });
  }, []);

  const handleError = (err: unknown) => {
    if (err instanceof UnauthorizedError) {
      onUnauthorized();
    } else {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  };

  const runDiscovery = async (event: React.FormEvent) => {
    event.preventDefault();
    const names = [firstArtist, secondArtist]
      .map((name) => name.trim())
      .filter(Boolean);
    if (names.length === 0 || searching) {
      return;
    }
    setSearching(true);
    setError(null);
    setSuggestions([]);
    try {
      const result = await discoverVenues(names);
      setSuggestions(result.suggestions);
      setReview(result.suggestions.map(() => "pending"));
      setSearched(true);
    } catch (err) {
      handleError(err);
    } finally {
      setSearching(false);
    }
  };

  const accept = async (index: number) => {
    setReview((states) =>
      states.map((s, i) => (i === index ? "accepting" : s)),
    );
    try {
      await acceptSuggestion(suggestions[index]);
      setReview((states) =>
        states.map((s, i) => (i === index ? "accepted" : s)),
      );
    } catch (err) {
      setReview((states) =>
        states.map((s, i) => (i === index ? "pending" : s)),
      );
      handleError(err);
    }
  };

  const dismiss = (index: number) => {
    setReview((states) =>
      states.map((s, i) => (i === index ? "dismissed" : s)),
    );
  };

  const visible = suggestions
    .map((suggestion, index) => ({ suggestion, index, state: review[index] }))
    .filter(({ state }) => state !== "dismissed");

  return (
    <div className="scouting-page">
      <header className="scouting-header">
        <div>
          <p className="scouting-overline">Season 2027</p>
          <h1 className="scouting-title">Scouting</h1>
        </div>
        <button className="scouting-back" onClick={onBack}>
          Back to venues
        </button>
      </header>

      <main className="scouting-main">
        <p className="scouting-lede">
          Follow the artists we admire — every stage they have played is a
          lead for us. Name one or two reference artists and Claude will
          search the manouche and swing circuit for the venues behind their
          tour dates.
        </p>

        <form className="scouting-form" onSubmit={runDiscovery}>
          <label className="scouting-label">
            Reference artist
            <input
              className="scouting-input"
              list="known-artists"
              value={firstArtist}
              onChange={(e) => setFirstArtist(e.target.value)}
              placeholder="e.g. Rhythm Future Quartet"
              required
            />
          </label>
          <label className="scouting-label">
            Second artist <span className="scouting-optional">optional</span>
            <input
              className="scouting-input"
              list="known-artists"
              value={secondArtist}
              onChange={(e) => setSecondArtist(e.target.value)}
              placeholder="Another band from the scene"
            />
          </label>
          <datalist id="known-artists">
            {artists.map((artist) => (
              <option key={artist.id} value={artist.name} />
            ))}
          </datalist>
          <button
            className="scouting-submit"
            type="submit"
            disabled={searching || !firstArtist.trim()}
          >
            {searching ? "Scouting…" : "Find venues"}
          </button>
        </form>

        {searching && (
          <p className="scouting-status">
            Claude is searching the circuit — this can take a minute or two.
          </p>
        )}
        {error && <p className="scouting-error">{error}</p>}

        {!searching && searched && visible.length === 0 && (
          <p className="scouting-status">
            Nothing left to review. Run another search or return to the
            board.
          </p>
        )}

        {visible.length > 0 && (
          <section className="scouting-results" aria-label="Suggested venues">
            <h2 className="scouting-results-title">
              For review
              <span className="scouting-results-count">{visible.length}</span>
            </h2>
            <p className="scouting-results-note">
              Nothing joins the pipeline until you accept it.
            </p>
            {visible.map(({ suggestion, index, state }) => {
              const place = [suggestion.city, suggestion.country]
                .filter(Boolean)
                .join(", ");
              return (
                <article className="suggestion-card" key={index}>
                  <h3 className="suggestion-name">{suggestion.name}</h3>
                  <p className="suggestion-meta">
                    {TYPE_LABELS[suggestion.type]}
                    {place && ` · ${place}`}
                  </p>
                  {suggestion.artist && (
                    <p className="suggestion-artist">
                      {suggestion.artist} played here
                    </p>
                  )}
                  {(suggestion.website || suggestion.source_url) && (
                    <p className="suggestion-links">
                      {suggestion.website && (
                        <a
                          href={suggestion.website}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Website
                        </a>
                      )}
                      {suggestion.source_url && (
                        <a
                          href={suggestion.source_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Source
                        </a>
                      )}
                    </p>
                  )}
                  {suggestion.already_in_pipeline ? (
                    <p className="suggestion-known">
                      Already in the pipeline
                      {suggestion.matched_venue_name &&
                        ` as “${suggestion.matched_venue_name}”`}
                    </p>
                  ) : state === "accepted" ? (
                    <p className="suggestion-accepted">Added to the pipeline</p>
                  ) : (
                    <div className="suggestion-actions">
                      <button
                        className="suggestion-accept"
                        disabled={state === "accepting"}
                        onClick={() => accept(index)}
                      >
                        {state === "accepting" ? "Adding…" : "Add to pipeline"}
                      </button>
                      <button
                        className="suggestion-dismiss"
                        onClick={() => dismiss(index)}
                      >
                        Dismiss
                      </button>
                    </div>
                  )}
                  {suggestion.already_in_pipeline && (
                    <div className="suggestion-actions">
                      <button
                        className="suggestion-dismiss"
                        onClick={() => dismiss(index)}
                      >
                        Dismiss
                      </button>
                    </div>
                  )}
                </article>
              );
            })}
          </section>
        )}
      </main>
    </div>
  );
}
