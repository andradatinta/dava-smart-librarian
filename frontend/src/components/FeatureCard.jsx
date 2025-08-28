const FeatureCard = ({ icon: Icon, title, description }) => {
  return (
    <div className="rounded-2xl p-4 shadow-sm hover:shadow-md transition-all duration-200 border border-orange-100/60 bg-white/70">
    <div className="text-center">
      <div className="inline-flex p-2.5 bg-gradient-to-br from-amber-100 to-orange-100 rounded-xl mb-3 shadow-sm">
        <Icon className="w-5 h-5 text-amber-700" />
      </div>
      <h3 className="font-semibold text-amber-900 text-sm">{title}</h3>
      <p className="text-amber-700/70 text-xs mt-1">{description}</p>
    </div>
  </div>
  )
}

export default FeatureCard
