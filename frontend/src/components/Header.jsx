import { Book } from "lucide-react";

const Header = () => {
  return (
    <div className="text-center">
    <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-amber-100/70 backdrop-blur-sm rounded-full text-amber-800 font-medium mb-4 border border-amber-200/50">
      <Book className="w-4 h-4" />
      Dava The Librarian
    </div>
    <h1 className="text-4xl md:text-5xl font-extrabold text-amber-900 leading-tight">
      Find your next book <span className="text-orange-700">📚</span>
    </h1>
    <p className="text-amber-700/80 text-base md:text-lg mt-2 max-w-xl mx-auto">
      Describe a theme, vibe, or mood. I’ll pick one perfect title from my
      collection.
    </p>
  </div>
  )
}

export default Header
