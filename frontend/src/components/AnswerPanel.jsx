import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import axios from "axios";
import { Book } from "lucide-react";
import { useState } from "react";
import { API_BASE } from "../App";

const AnswerPanel = ({ response, loading }) => {
  const hasTitle = Boolean(response?.title);
  const [speaking, setSpeaking] = useState(false);
  const answerText = response?.answer || "";

  const playTTS = async () => {
    if (!answerText.trim() || speaking) return;
    try {
      setSpeaking(true);
      const res = await axios.post(
        `${API_BASE}/tts`,
        { text: answerText, voice: "alloy" },
        { responseType: "arraybuffer" } 
      );
      const blob = new Blob([res.data], { type: "audio/mpeg" });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setSpeaking(false);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        setSpeaking(false);
      };
      await audio.play();
    } catch (e) {
      console.error("TTS play error:", e);
      setSpeaking(false);
    }
  };
  return (
    <div className="w-full max-w-4xl place-self-center">
      <div className="rounded-2xl bg-white/80 border border-amber-200/50 shadow-md p-5">
        {loading ? (
          <div className="flex items-center justify-center py-8 text-amber-700">
            <div className="w-5 h-5 border-2 border-amber-300 border-t-amber-700 rounded-full animate-spin mr-3" />
            <span className="text-sm">Finding your perfect book…</span>
          </div>
        ) : (
          <div className="flex items-start gap-3">
            <div className="p-2.5 bg-gradient-to-br from-amber-100 to-orange-100 rounded-xl shadow-sm">
              <Book className="w-5 h-5 text-amber-700" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                {hasTitle ? (
                  <div>
                    <h3 className="text-base font-semibold text-amber-900">
                      Your Book Recommendation
                    </h3>
                    <div className="font-semibold text-amber-900">
                      {response.title}
                    </div>
                  </div>
                ) : (
                  <h3 className="text-base font-semibold text-amber-900">
                    Message
                  </h3>
                )}
                <button
                  onClick={playTTS}
                  disabled={!answerText || speaking}
                  className={`ml-3 px-3 py-1.5 rounded-lg text-sm font-medium shadow
                    ${
                      speaking
                        ? "bg-amber-300  text-amber-900 cursor-not-allowed"
                        : "bg-amber-600 hover:bg-amber-700 text-amber-900"
                    }`}
                  title="Listen to this answer"
                >
                  {speaking ? "Playing…" : "Listen 🔊"}
                </button>
              </div>

              <div className="text-amber-900/90 text-base leading-relaxed max-h-[38vh] overflow-auto">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {answerText || "No recommendation found."}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
export default AnswerPanel;
