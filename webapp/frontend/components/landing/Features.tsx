export default function Features() {
  const features = [
    {
      title: "Scraping Automatizado",
      description: "Monitorea +50 fuentes de noticias en tiempo real, 24/7",
      icon: "🔄",
      gradient: "from-blue-500 to-cyan-500",
    },
    {
      title: "IA de Última Generación",
      description: "Powered by GPT-4 para curación y ranking de contenido premium",
      icon: "🧠",
      gradient: "from-purple-500 to-pink-500",
    },
    {
      title: "Entrega Personalizada",
      description: "Tu newsletter en tu bandeja cada mañana, adaptado a tus intereses",
      icon: "📬",
      gradient: "from-orange-500 to-red-500",
    },
    {
      title: "Zero Duplicados",
      description: "Agrupación semántica inteligente elimina noticias repetidas",
      icon: "🔗",
      gradient: "from-green-500 to-emerald-500",
    },
    {
      title: "Filtrado Preciso",
      description: "Categorías personalizables: economía, política, tech y más",
      icon: "🎯",
      gradient: "from-yellow-500 to-orange-500",
    },
    {
      title: "Ultra Eficiente",
      description: "Tecnología optimizada, resultados profesionales",
      icon: "⚡",
      gradient: "from-indigo-500 to-purple-500",
    },
  ];

  return (
    <section id="features" className="py-24 px-4 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 relative overflow-hidden">
      {/* Decoración de fondo */}
      <div className="absolute top-0 left-0 w-96 h-96 bg-purple-600 rounded-full blur-3xl opacity-10 -translate-x-1/2 -translate-y-1/2" />
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-pink-600 rounded-full blur-3xl opacity-10 translate-x-1/2 translate-y-1/2" />

      {/* Grid pattern */}
      <div className="absolute inset-0 opacity-[0.02]" style={{
        backgroundImage: `linear-gradient(rgba(255, 255, 255, 0.3) 1px, transparent 1px),
                         linear-gradient(90deg, rgba(255, 255, 255, 0.3) 1px, transparent 1px)`,
        backgroundSize: '50px 50px'
      }} />

      <div className="max-w-7xl mx-auto relative z-10">
        <div className="text-center mb-16">
          <div className="inline-block mb-4 px-4 py-2 bg-purple-500/20 backdrop-blur-sm rounded-full border border-purple-400/30">
            <span className="text-purple-300 text-sm font-semibold">✨ CARACTERÍSTICAS</span>
          </div>
          <h2 className="text-5xl md:text-6xl font-black mb-6 text-white">
            Todo lo que necesitas
          </h2>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Tecnología de vanguardia para mantenerte informado sin esfuerzo
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, idx) => (
            <div
              key={idx}
              className="group relative p-8 bg-slate-800/50 backdrop-blur-sm rounded-2xl border border-slate-700 hover:border-purple-500/50 hover:shadow-2xl hover:shadow-purple-500/20 transition-all duration-300 hover:-translate-y-2"
            >
              {/* Gradiente de fondo en hover */}
              <div className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-10 rounded-2xl transition-opacity`} />

              {/* Contenido */}
              <div className="relative">
                <div className="text-6xl mb-6 transform group-hover:scale-110 transition-transform">
                  {feature.icon}
                </div>
                <h3 className="text-2xl font-bold mb-3 text-white">
                  {feature.title}
                </h3>
                <p className="text-gray-400 leading-relaxed">
                  {feature.description}
                </p>
              </div>

              {/* Indicador de esquina */}
              <div className={`absolute top-4 right-4 w-2 h-2 bg-gradient-to-br ${feature.gradient} rounded-full opacity-0 group-hover:opacity-100 transition-opacity`} />
            </div>
          ))}
        </div>

        {/* Stats adicionales */}
        <div className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-8">
          <div className="text-center p-6 bg-slate-800/30 backdrop-blur-sm rounded-xl border border-slate-700/50">
            <div className="text-4xl font-black bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent mb-2">50+</div>
            <div className="text-gray-400">Fuentes Verificadas</div>
          </div>
          <div className="text-center p-6 bg-slate-800/30 backdrop-blur-sm rounded-xl border border-slate-700/50">
            <div className="text-4xl font-black bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent mb-2">24/7</div>
            <div className="text-gray-400">Monitoreo Continuo</div>
          </div>
          <div className="text-center p-6 bg-slate-800/30 backdrop-blur-sm rounded-xl border border-slate-700/50">
            <div className="text-4xl font-black bg-gradient-to-r from-orange-400 to-red-400 bg-clip-text text-transparent mb-2">5min</div>
            <div className="text-gray-400">Tiempo de Lectura</div>
          </div>
          <div className="text-center p-6 bg-slate-800/30 backdrop-blur-sm rounded-xl border border-slate-700/50">
            <div className="text-4xl font-black bg-gradient-to-r from-green-400 to-emerald-400 bg-clip-text text-transparent mb-2">100%</div>
            <div className="text-gray-400">Curado con IA</div>
          </div>
        </div>
      </div>
    </section>
  );
}
