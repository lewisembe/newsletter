export default function Preview() {
  return (
    <section className="py-20 px-4 bg-gradient-to-b from-slate-950 to-slate-900 relative overflow-hidden">
      {/* Decoración de fondo */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-px bg-gradient-to-r from-transparent via-purple-500/50 to-transparent" />

      <div className="max-w-6xl mx-auto relative z-10">
        <div className="text-center mb-12">
          <div className="inline-block mb-4 px-4 py-2 bg-purple-500/10 backdrop-blur-sm rounded-full border border-purple-400/20">
            <span className="text-purple-300 text-sm font-semibold">📰 VISTA PREVIA</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-black mb-4 text-white">
            Así se ve tu <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">Newsletter</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Contenido profesional y bien organizado, listo para consumir en minutos
          </p>
        </div>

        {/* Newsletter mockup */}
        <div className="relative max-w-4xl mx-auto">
          {/* Glow effect */}
          <div className="absolute inset-0 bg-gradient-to-r from-purple-600/30 via-pink-600/30 to-orange-600/30 blur-3xl opacity-40 animate-pulse" />

          {/* Newsletter card */}
          <div className="relative bg-white rounded-2xl shadow-2xl overflow-hidden border border-gray-200">
            {/* Header del newsletter */}
            <div className="bg-gradient-to-r from-purple-600 via-pink-600 to-orange-600 p-8 text-white">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-3xl font-black">Briefy</h3>
                <span className="px-3 py-1 bg-white/20 backdrop-blur-sm rounded-full text-sm">
                  {new Date().toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}
                </span>
              </div>
              <p className="text-white/90">Tu resumen diario de noticias</p>
            </div>

            {/* Contenido del newsletter */}
            <div className="p-8 space-y-6">
              {/* Artículo 1 */}
              <article className="group hover:bg-gray-50 p-4 rounded-lg transition-colors cursor-pointer">
                <div className="flex gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-24 h-24 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-semibold rounded">ECONOMÍA</span>
                      <span className="text-gray-400 text-sm">• 3 min lectura</span>
                    </div>
                    <h4 className="text-xl font-bold text-gray-900 mb-2 group-hover:text-purple-600 transition-colors">
                      Nuevas regulaciones financieras impactan el mercado europeo
                    </h4>
                    <p className="text-gray-600 text-sm line-clamp-2">
                      Los mercados reaccionan ante el anuncio de nuevas medidas regulatorias que podrían cambiar el panorama financiero...
                    </p>
                  </div>
                </div>
              </article>

              {/* Divider */}
              <div className="border-t border-gray-200" />

              {/* Artículo 2 */}
              <article className="group hover:bg-gray-50 p-4 rounded-lg transition-colors cursor-pointer">
                <div className="flex gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-24 h-24 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs font-semibold rounded">TECNOLOGÍA</span>
                      <span className="text-gray-400 text-sm">• 2 min lectura</span>
                    </div>
                    <h4 className="text-xl font-bold text-gray-900 mb-2 group-hover:text-purple-600 transition-colors">
                      Avances en IA generativa transforman industrias creativas
                    </h4>
                    <p className="text-gray-600 text-sm line-clamp-2">
                      Nuevos modelos de inteligencia artificial están revolucionando la forma en que creamos contenido digital...
                    </p>
                  </div>
                </div>
              </article>

              {/* Divider */}
              <div className="border-t border-gray-200" />

              {/* Artículo 3 */}
              <article className="group hover:bg-gray-50 p-4 rounded-lg transition-colors cursor-pointer">
                <div className="flex gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-24 h-24 bg-gradient-to-br from-orange-500 to-red-500 rounded-lg" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2 py-1 bg-orange-100 text-orange-700 text-xs font-semibold rounded">POLÍTICA</span>
                      <span className="text-gray-400 text-sm">• 4 min lectura</span>
                    </div>
                    <h4 className="text-xl font-bold text-gray-900 mb-2 group-hover:text-purple-600 transition-colors">
                      Cumbre internacional aborda desafíos climáticos urgentes
                    </h4>
                    <p className="text-gray-600 text-sm line-clamp-2">
                      Líderes mundiales se reúnen para discutir estrategias concretas frente al cambio climático...
                    </p>
                  </div>
                </div>
              </article>
            </div>

            {/* Footer del newsletter */}
            <div className="bg-gray-50 p-6 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-600">
                  <span className="font-semibold">12 artículos</span> seleccionados especialmente para ti
                </div>
                <button className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg font-semibold hover:shadow-lg transition-shadow text-sm">
                  Leer Newsletter Completo
                </button>
              </div>
            </div>
          </div>

          {/* Floating badges */}
          <div className="absolute -top-6 -left-6 bg-white rounded-xl shadow-xl p-4 border border-gray-200 hidden lg:block">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-500 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              </div>
              <div>
                <div className="text-xs text-gray-500">Contenido</div>
                <div className="font-bold text-gray-900">100% Verificado</div>
              </div>
            </div>
          </div>

          <div className="absolute -bottom-6 -right-6 bg-white rounded-xl shadow-xl p-4 border border-gray-200 hidden lg:block">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 5a2 2 0 012-2h7a2 2 0 012 2v4a2 2 0 01-2 2H9l-3 3v-3H4a2 2 0 01-2-2V5z" />
                  <path d="M15 7v2a4 4 0 01-4 4H9.828l-1.766 1.767c.28.149.599.233.938.233h2l3 3v-3h2a2 2 0 002-2V9a2 2 0 00-2-2h-1z" />
                </svg>
              </div>
              <div>
                <div className="text-xs text-gray-500">Resumen</div>
                <div className="font-bold text-gray-900">5 min lectura</div>
              </div>
            </div>
          </div>
        </div>

        {/* Call to action secundario */}
        <div className="text-center mt-16">
          <p className="text-gray-400 mb-4">Únete a miles de lectores informados</p>
          <div className="flex items-center justify-center gap-4">
            <div className="flex -space-x-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="w-10 h-10 bg-gradient-to-br from-purple-400 to-pink-400 rounded-full border-2 border-slate-900" />
              ))}
            </div>
            <span className="text-gray-300 font-semibold">+5,000 suscriptores activos</span>
          </div>
        </div>
      </div>
    </section>
  );
}
