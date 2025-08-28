import FeatureCard from './FeatureCard'
import { Sparkles, Book, MessageCircle } from 'lucide-react'

const FeaturePresentationRow = () => {
  return (
    <div className="grid grid-cols-3 gap-3 w-full max-w-5xl">
    <FeatureCard
      icon={MessageCircle}
      title="Smart Search"
      description="Semantic match on your vector DB."
    />
    <FeatureCard
      icon={Sparkles}
      title="Any Language"
      description="Answers in the language you use."
    />
    <FeatureCard
      icon={Book}
      title="One Pick"
      description="Single, confident recommendation."
    />
  </div>
  )
}

export default FeaturePresentationRow
