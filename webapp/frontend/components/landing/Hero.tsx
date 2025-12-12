import Link from 'next/link';

export default function Hero() {
  return (
    <section className="relative min-h-[90vh] flex items-center px-4 overflow-hidden bg-gradient-to-br from-slate-950 via-purple-950 to-slate-950">
      {/* Imagen de fondo: redacción de periódico vintage años 90 */}
      <div
        className="absolute inset-0 bg-cover bg-center opacity-20"
        style={{
          backgroundImage: 'url(https://images.unsplash.com/photo-1495020689067-958852a7765e?w=1920&q=85&fm=jpg)',
          filter: 'grayscale(80%) sepia(20%) blur(0.8px)',
          mixBlendMode: 'overlay'
        }}
      />

      {/* Grid pattern overlay */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: `linear-gradient(rgba(168, 85, 247, 0.4) 1px, transparent 1px),
                         linear-gradient(90deg, rgba(168, 85, 247, 0.4) 1px, transparent 1px)`,
        backgroundSize: '40px 40px'
      }} />

      {/* Gradient orbs */}
      <div className="absolute top-20 left-20 w-96 h-96 bg-purple-600 rounded-full blur-[120px] opacity-20 animate-pulse" />
      <div className="absolute bottom-20 right-20 w-96 h-96 bg-pink-600 rounded-full blur-[120px] opacity-20 animate-pulse" style={{animationDelay: '2s'}} />

      <div className="max-w-6xl mx-auto relative z-10 w-full">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          {/* Columna izquierda: Texto */}
          <div className="text-left">
            <div className="inline-block mb-4 px-4 py-2 bg-purple-500/20 backdrop-blur-sm rounded-full border border-purple-400/30">
              <span className="text-purple-200 text-sm font-medium">✨ Powered by AI</span>
            </div>

            <h1 className="text-7xl md:text-8xl font-black mb-6 leading-none tracking-tight">
              <span className="text-white drop-shadow-2xl">Brief</span>
              <span
                className="drop-shadow-2xl"
                style={{
                  background: 'linear-gradient(135deg, #a855f7, #ec4899, #f97316)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text'
                }}
              >
                y
              </span>
            </h1>

            <p className="text-xl md:text-2xl text-gray-200 mb-8 leading-relaxed max-w-xl">
              Tu dosis diaria de <span className="text-purple-300 font-bold">información relevante</span>.
              <br />
              <span className="text-gray-400">Curado por IA, entregado cada mañana.</span>
            </p>

            <div className="flex gap-4 flex-wrap">
              <Link
                href="/login"
                className="group px-8 py-4 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-xl font-bold text-lg hover:shadow-2xl hover:shadow-purple-500/50 transition-all hover:scale-105 inline-flex items-center gap-2"
              >
                Comenzar Gratis
                <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </Link>
              <a
                href="#features"
                className="px-8 py-4 bg-white/10 backdrop-blur-sm text-white border-2 border-white/20 rounded-xl font-bold text-lg hover:bg-white/20 transition-all inline-block"
              >
                Ver Demo
              </a>
            </div>

            {/* Stats */}
            <div className="mt-12 grid grid-cols-3 gap-6">
              <div>
                <div className="text-3xl font-bold text-white">50+</div>
                <div className="text-sm text-gray-400">Fuentes</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-white">100%</div>
                <div className="text-sm text-gray-400">IA Curada</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-white">5min</div>
                <div className="text-sm text-gray-400">Lectura</div>
              </div>
            </div>
          </div>

          {/* Columna derecha: Ícono/Mockup */}
          <div className="relative hidden md:block">
            <div className="relative mx-auto w-80 h-80 flex items-center justify-center">
              {/* Círculos animados de fondo */}
              <div className="absolute inset-0 bg-gradient-to-tr from-purple-500/20 to-pink-500/20 rounded-full blur-3xl animate-pulse" />
              <div className="absolute inset-10 bg-gradient-to-bl from-blue-500/20 to-purple-500/20 rounded-full blur-2xl animate-pulse" style={{animationDelay: '1s'}} />

              {/* Ícono principal */}
              <svg
                className="w-64 h-64 relative z-10 drop-shadow-2xl"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M9 12h6M9 16h6M13 4H7C5.89543 4 5 4.89543 5 6v12c0 1.1046.89543 2 2 2h10c1.1046 0 2-.8954 2-2V10l-6-6z"
                  stroke="url(#gradient1)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M13 4v6h6"
                  stroke="url(#gradient1)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <defs>
                  <linearGradient id="gradient1" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#a855f7" />
                    <stop offset="50%" stopColor="#ec4899" />
                    <stop offset="100%" stopColor="#f97316" />
                  </linearGradient>
                </defs>
              </svg>

              {/* Badge estrella */}
              <div className="absolute top-10 right-10 flex items-center justify-center w-20 h-20 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full shadow-2xl shadow-orange-500/50 animate-bounce">
                <svg className="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
