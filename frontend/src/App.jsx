import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import axios from "axios";
import Header from "./components/Header";
import ChatBar from "./components/ChatBar";
import AnswerPanel from "./components/AnswerPanel";
import FeaturePresentationRow from "./components/FeaturePresentationRow";

export const API_BASE =
  import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const StatusLine = () => (
  <div className="text-center text-[11px] text-amber-700/60">
    Connected to a{" "}
    <code className="bg-amber-100/70 px-2 py-0.5 rounded font-mono">
      FastAPI
    </code>
    server
  </div>
);

const toUiResponse = (api) => ({
  answer: String(api?.answer || ""),
  title: api?.chosen_title || null,
  context: Array.isArray(api?.context_used) ? api.context_used : [],
});

export default function App() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState({
    answer: "",
    title: null,
    context: [],
  });
  const [loading, setLoading] = useState(false);
  const hasAsked = loading || !!response.answer;

  const ask = async () => {
    if (!query.trim() || loading) return;
    setLoading(true);
    setResponse({ answer: "", title: null, context: [] });
    try {
      const { data } = await axios.post(
        `${API_BASE}/chat`,
        { query: query.trim(), k: 3 },
        { headers: { "Content-Type": "application/json" } }
      );
      setResponse(toUiResponse(data));
    } catch (e) {
      setResponse({
        answer:
          "Sorry, I couldn't process your request right now. Please try again.",
        title: null,
        context: [],
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-dvh w-screen bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50 overflow-hidden">
      <div className="h-full grid grid-rows-[auto_auto_1fr_auto_auto] items-center justify-items-center gap-4 px-4 sm:px-6 py-4">
        <Header />
        <AnimatePresence>
          {!hasAsked && (
            <motion.div
              key="features"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.28, ease: "easeInOut" }}
              className="w-full flex justify-center"
            >
              <FeaturePresentationRow />
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence mode="wait">
          {(loading || response.answer) && (
            <motion.div
              key={loading ? "answer-loading" : "answer-ready"}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              transition={{ duration: 0.28, ease: "easeInOut" }}
              className="flex items-center justify-center w-full h-full"
            >
              <AnswerPanel response={response} loading={loading} />
            </motion.div>
          )}
        </AnimatePresence>

        <ChatBar
          value={query}
          onChange={setQuery}
          onSubmit={ask}
          disabled={loading}
        />

        <StatusLine />
      </div>
    </div>
  );
}
