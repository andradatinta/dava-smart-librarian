import { Send } from "lucide-react";

const ChatBar = ({ value, onChange, onSubmit, disabled }) => {
  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onSubmit();
    }
  };
  return (
    <div className="w-full max-w-5xl place-self-center">
      <div className="bg-gradient-to-r from-amber-50/90 to-orange-50/90 backdrop-blur-sm rounded-2xl shadow-md border border-amber-200/40 p-2.5">
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="something cozy for autumn evenings… / o poveste despre prietenie…"
            className="flex-1 bg-transparent px-4 py-3 text-amber-900 placeholder-amber-500/60 focus:outline-none text-base"
            disabled={disabled}
          />
          <button
            onClick={onSubmit}
            disabled={disabled || !value.trim()}
            className="bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 disabled:from-amber-300 disabled:to-orange-300 disabled:cursor-not-allowed text-white px-5 py-3 rounded-xl font-medium transition-all duration-200 flex items-center gap-2 shadow"
          >
            {disabled ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            Ask
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatBar
