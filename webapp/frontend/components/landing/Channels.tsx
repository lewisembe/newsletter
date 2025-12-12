export default function Channels() {
  return (
    <section className="py-24 px-4 bg-gradient-to-b from-slate-900 via-indigo-900 to-slate-900 relative overflow-hidden">
      {/* Decoración de fondo */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-purple-600 rounded-full blur-3xl opacity-20" />
      <div className="absolute bottom-0 left-0 w-96 h-96 bg-blue-600 rounded-full blur-3xl opacity-20" />

      {/* Grid pattern */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: `linear-gradient(rgba(255, 255, 255, 0.5) 1px, transparent 1px),
                         linear-gradient(90deg, rgba(255, 255, 255, 0.5) 1px, transparent 1px)`,
        backgroundSize: '50px 50px'
      }} />

      <div className="max-w-7xl mx-auto relative z-10">
        {/* Header */}
        <div className="text-center mb-16">
          <div className="inline-block mb-4 px-4 py-2 bg-indigo-500/20 backdrop-blur-sm rounded-full border border-indigo-400/30">
            <span className="text-indigo-300 text-sm font-semibold">📬 CANALES DE DISTRIBUCIÓN</span>
          </div>
          <h2 className="text-5xl md:text-6xl font-black mb-6 text-white leading-tight">
            Recibe tu newsletter
            <br />
            <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
              como tú prefieras
            </span>
          </h2>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed">
            Múltiples formas de acceder a tu información personalizada.
            Elige el canal que mejor se adapte a tu flujo de trabajo.
          </p>
        </div>

        {/* Grid de canales */}
        <div className="grid md:grid-cols-3 gap-8 mb-16">
          {/* Email */}
          <div className="group relative bg-gradient-to-br from-slate-800/80 to-slate-900/80 backdrop-blur-sm rounded-2xl p-8 border border-slate-700 hover:border-blue-500/50 transition-all duration-300 hover:-translate-y-2 hover:shadow-2xl hover:shadow-blue-500/20">
            {/* Glow effect */}
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-cyan-500 opacity-0 group-hover:opacity-10 rounded-2xl transition-opacity" />

            <div className="relative">
              {/* Icon */}
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center mb-6 transform group-hover:scale-110 transition-transform shadow-lg">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>

              <h3 className="text-2xl font-bold text-white mb-3">
                📧 Email
              </h3>
              <p className="text-gray-400 leading-relaxed mb-4">
                Newsletter automático en tu bandeja de entrada cada mañana.
                Compatible con Gmail, Outlook y cualquier cliente de correo.
              </p>

              <div className="space-y-2 text-sm">
                <div className="flex items-center text-cyan-300">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Entrega programada
                </div>
                <div className="flex items-center text-cyan-300">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  HTML responsive
                </div>
                <div className="flex items-center text-cyan-300">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Archivos adjuntos
                </div>
              </div>

              {/* Badge */}
              <div className="absolute top-6 right-6">
                <div className="bg-blue-500/20 backdrop-blur-sm px-2 py-1 rounded-full text-xs font-bold text-blue-300 border border-blue-400/30">
                  Clásico
                </div>
              </div>
            </div>
          </div>

          {/* Telegram */}
          <div className="group relative bg-gradient-to-br from-slate-800/80 to-slate-900/80 backdrop-blur-sm rounded-2xl p-8 border border-slate-700 hover:border-purple-500/50 transition-all duration-300 hover:-translate-y-2 hover:shadow-2xl hover:shadow-purple-500/20">
            {/* Glow effect */}
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500 to-pink-500 opacity-0 group-hover:opacity-10 rounded-2xl transition-opacity" />

            <div className="relative">
              {/* Icon */}
              <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center mb-6 transform group-hover:scale-110 transition-transform shadow-lg">
                <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121L7.78 13.73l-2.955-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.827z" />
                </svg>
              </div>

              <h3 className="text-2xl font-bold text-white mb-3">
                💬 Telegram
              </h3>
              <p className="text-gray-400 leading-relaxed mb-4">
                Bot automatizado que te envía el resumen directamente a Telegram.
                Notificaciones instantáneas y formato móvil optimizado.
              </p>

              <div className="space-y-2 text-sm">
                <div className="flex items-center text-purple-300">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Notificaciones push
                </div>
                <div className="flex items-center text-purple-300">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Enlaces directos
                </div>
                <div className="flex items-center text-purple-300">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Markdown nativo
                </div>
              </div>

              {/* Badge */}
              <div className="absolute top-6 right-6">
                <div className="bg-purple-500/20 backdrop-blur-sm px-2 py-1 rounded-full text-xs font-bold text-purple-300 border border-purple-400/30">
                  Instantáneo
                </div>
              </div>
            </div>
          </div>

          {/* Web App */}
          <div className="group relative bg-gradient-to-br from-slate-800/80 to-slate-900/80 backdrop-blur-sm rounded-2xl p-8 border border-slate-700 hover:border-emerald-500/50 transition-all duration-300 hover:-translate-y-2 hover:shadow-2xl hover:shadow-emerald-500/20">
            {/* Glow effect */}
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-500 to-teal-500 opacity-0 group-hover:opacity-10 rounded-2xl transition-opacity" />

            <div className="relative">
              {/* Icon */}
              <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-xl flex items-center justify-center mb-6 transform group-hover:scale-110 transition-transform shadow-lg">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                </svg>
              </div>

              <h3 className="text-2xl font-bold text-white mb-3">
                🌐 Web App
              </h3>
              <p className="text-gray-400 leading-relaxed mb-4">
                Dashboard interactivo con búsqueda, filtros y archivo histórico.
                Accede desde cualquier dispositivo con tu navegador.
              </p>

              <div className="space-y-2 text-sm">
                <div className="flex items-center text-emerald-300">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Búsqueda avanzada
                </div>
                <div className="flex items-center text-emerald-300">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Archivo histórico
                </div>
                <div className="flex items-center text-emerald-300">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Exportación PDF/Markdown
                </div>
              </div>

              {/* Badge */}
              <div className="absolute top-6 right-6">
                <div className="bg-emerald-500/20 backdrop-blur-sm px-2 py-1 rounded-full text-xs font-bold text-emerald-300 border border-emerald-400/30">
                  Interactivo
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Comparación y características adicionales */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-8 border border-slate-700">
          <h3 className="text-3xl font-bold text-white text-center mb-8">
            Usa todos los canales a la vez
          </h3>

          <div className="grid md:grid-cols-3 gap-6 mb-8">
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-12 h-12 bg-gradient-to-br from-cyan-500 to-blue-500 rounded-full mb-3">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </div>
              <h4 className="text-lg font-bold text-white mb-2">Multi-canal</h4>
              <p className="text-gray-400 text-sm">
                Activa Email, Telegram y Web App simultáneamente sin restricciones
              </p>
            </div>

            <div className="text-center">
              <div className="inline-flex items-center justify-center w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full mb-3">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                </svg>
              </div>
              <h4 className="text-lg font-bold text-white mb-2">Personalizable</h4>
              <p className="text-gray-400 text-sm">
                Configura horarios, formatos y contenido diferente para cada canal
              </p>
            </div>

            <div className="text-center">
              <div className="inline-flex items-center justify-center w-12 h-12 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-full mb-3">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <h4 className="text-lg font-bold text-white mb-2">Privacidad Total</h4>
              <p className="text-gray-400 text-sm">
                Todos los datos quedan en tu servidor. Sin tracking ni analytics externos
              </p>
            </div>
          </div>

          <div className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 rounded-xl p-6 text-center">
            <p className="text-white text-lg font-semibold mb-2">
              ✨ Mismo contenido, diferentes formatos
            </p>
            <p className="text-indigo-100 text-sm">
              Email para la rutina matinal • Telegram para noticias urgentes • Web App para investigación profunda
            </p>
          </div>
        </div>

        {/* CTA */}
        <div className="mt-12 text-center">
          <a
            href="#cta"
            className="inline-flex items-center justify-center px-8 py-4 bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-500 text-white rounded-full font-bold text-lg hover:shadow-2xl hover:shadow-blue-500/50 transition-all hover:scale-105"
          >
            <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Empezar a Recibir Newsletters
          </a>
        </div>
      </div>
    </section>
  );
}
