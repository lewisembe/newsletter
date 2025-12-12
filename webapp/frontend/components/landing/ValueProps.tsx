export default function ValueProps() {
  return (
    <section className="py-24 px-4 bg-gradient-to-b from-white to-gray-50 relative overflow-hidden">
      {/* Decoración sutil */}
      <div className="absolute top-20 right-10 w-72 h-72 bg-indigo-100 rounded-full blur-3xl opacity-30" />
      <div className="absolute bottom-20 left-10 w-72 h-72 bg-purple-100 rounded-full blur-3xl opacity-30" />

      <div className="max-w-7xl mx-auto relative z-10">
        {/* Header */}
        <div className="text-center mb-20">
          <div className="inline-block mb-4 px-4 py-2 bg-indigo-100 rounded-full">
            <span className="text-indigo-700 text-sm font-semibold">🎯 NUESTRO VALOR</span>
          </div>
          <h2 className="text-5xl md:text-6xl font-black mb-6 text-gray-900">
            Información que importa,
            <br />
            <span className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              contada completa
            </span>
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
            No más titulares sensacionalistas ni piezas a medias.
            Te ofrecemos el contexto completo para que entiendas lo que realmente está pasando.
          </p>
        </div>

        {/* Historias Completas */}
        <div className="mb-20">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            {/* Contenido */}
            <div className="order-2 md:order-1">
              <div className="inline-block mb-4 px-3 py-1 bg-orange-100 text-orange-700 rounded-full text-sm font-semibold">
                📚 Historias Completas
              </div>
              <h3 className="text-4xl font-bold mb-6 text-gray-900">
                Toda la historia, no solo el titular
              </h3>
              <p className="text-lg text-gray-700 mb-6 leading-relaxed">
                Los temas candentes merecen más que un tweet. Agrupamos automáticamente noticias relacionadas
                para darte <strong>la historia completa desde múltiples ángulos</strong>.
              </p>
              <ul className="space-y-4">
                <li className="flex items-start">
                  <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center text-white font-bold mr-3 mt-1">
                    1
                  </div>
                  <div>
                    <strong className="text-gray-900">Clustering Inteligente:</strong>
                    <span className="text-gray-600 ml-2">
                      Agrupamos noticias sobre el mismo tema usando IA semántica
                    </span>
                  </div>
                </li>
                <li className="flex items-start">
                  <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center text-white font-bold mr-3 mt-1">
                    2
                  </div>
                  <div>
                    <strong className="text-gray-900">Contexto Temporal:</strong>
                    <span className="text-gray-600 ml-2">
                      Entendemos cómo evoluciona una historia en el tiempo
                    </span>
                  </div>
                </li>
                <li className="flex items-start">
                  <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center text-white font-bold mr-3 mt-1">
                    3
                  </div>
                  <div>
                    <strong className="text-gray-900">Síntesis Ejecutiva:</strong>
                    <span className="text-gray-600 ml-2">
                      Resumen conciso con los puntos clave de todas las fuentes
                    </span>
                  </div>
                </li>
              </ul>
            </div>

            {/* Visual */}
            <div className="order-1 md:order-2">
              <div className="relative">
                <div className="bg-white rounded-2xl shadow-2xl p-6 border border-gray-200">
                  <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-200">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                      <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                      <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                    </div>
                    <span className="text-xs text-gray-500 font-mono">cluster_20250104_a8f3</span>
                  </div>

                  <div className="mb-4">
                    <div className="inline-block px-2 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded mb-2">
                      🔥 Tema Candente
                    </div>
                    <h4 className="font-bold text-lg text-gray-900 mb-2">
                      Crisis Energética Europea
                    </h4>
                    <p className="text-sm text-gray-600 mb-3">
                      8 fuentes · 15 artículos · Actualizado hace 2h
                    </p>
                  </div>

                  <div className="space-y-2 mb-4">
                    <div className="flex items-center text-xs text-gray-600">
                      <div className="w-1.5 h-1.5 bg-blue-500 rounded-full mr-2"></div>
                      Financial Times, El País, Le Monde
                    </div>
                    <div className="flex items-center text-xs text-gray-600">
                      <div className="w-1.5 h-1.5 bg-green-500 rounded-full mr-2"></div>
                      Bloomberg, Expansión, BBC
                    </div>
                    <div className="flex items-center text-xs text-gray-600">
                      <div className="w-1.5 h-1.5 bg-purple-500 rounded-full mr-2"></div>
                      El Confidencial, The Economist
                    </div>
                  </div>

                  <div className="bg-gradient-to-r from-indigo-50 to-purple-50 p-3 rounded-lg border border-indigo-200">
                    <p className="text-xs text-gray-700 leading-relaxed">
                      <strong>Síntesis:</strong> Los precios del gas natural europeo aumentaron un 15%
                      tras el anuncio de restricciones en el suministro ruso...
                    </p>
                  </div>
                </div>

                {/* Badge flotante */}
                <div className="absolute -top-4 -right-4 bg-gradient-to-br from-orange-500 to-red-500 text-white px-4 py-2 rounded-full shadow-lg text-sm font-bold">
                  15 artículos → 1 historia
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Neutralidad Informativa */}
        <div>
          <div className="grid md:grid-cols-2 gap-12 items-center">
            {/* Visual */}
            <div>
              <div className="relative">
                <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl shadow-2xl p-8 border border-slate-700">
                  <div className="text-center mb-6">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-emerald-400 to-teal-400 rounded-full mb-4">
                      <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <h4 className="text-2xl font-bold text-white mb-2">Balance Editorial</h4>
                    <p className="text-gray-400 text-sm">Análisis de 50+ fuentes</p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>Centradas</span>
                        <span>65%</span>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-blue-400 to-cyan-400" style={{width: '65%'}}></div>
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>Progresistas</span>
                        <span>18%</span>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-purple-400 to-pink-400" style={{width: '18%'}}></div>
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>Conservadoras</span>
                        <span>17%</span>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-orange-400 to-red-400" style={{width: '17%'}}></div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-6 pt-6 border-t border-slate-700 flex items-center justify-center">
                    <svg className="w-5 h-5 text-emerald-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    <span className="text-emerald-400 font-semibold text-sm">Verificado por IA</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Contenido */}
            <div>
              <div className="inline-block mb-4 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-sm font-semibold">
                ⚖️ Neutralidad Informativa
              </div>
              <h3 className="text-4xl font-bold mb-6 text-gray-900">
                Todos los ángulos, sin sesgos
              </h3>
              <p className="text-lg text-gray-700 mb-6 leading-relaxed">
                Monitoreamos fuentes de todo el espectro editorial. Nuestra IA analiza el tono,
                el enfoque y la cobertura para darte <strong>una visión equilibrada</strong> de cada tema.
              </p>
              <ul className="space-y-4">
                <li className="flex items-start">
                  <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-lg flex items-center justify-center text-white text-xl mr-3 mt-1">
                    🌍
                  </div>
                  <div>
                    <strong className="text-gray-900">Diversidad de Fuentes:</strong>
                    <span className="text-gray-600 ml-2">
                      Medios locales, internacionales, especializados y generalistas
                    </span>
                  </div>
                </li>
                <li className="flex items-start">
                  <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-lg flex items-center justify-center text-white text-xl mr-3 mt-1">
                    🎭
                  </div>
                  <div>
                    <strong className="text-gray-900">Detección de Sesgos:</strong>
                    <span className="text-gray-600 ml-2">
                      Identificamos automáticamente el tono editorial y compensamos
                    </span>
                  </div>
                </li>
                <li className="flex items-start">
                  <div className="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-lg flex items-center justify-center text-white text-xl mr-3 mt-1">
                    📊
                  </div>
                  <div>
                    <strong className="text-gray-900">Transparencia Total:</strong>
                    <span className="text-gray-600 ml-2">
                      Siempre indicamos las fuentes originales y su orientación
                    </span>
                  </div>
                </li>
              </ul>

              <div className="mt-8 p-4 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl border border-emerald-200">
                <p className="text-sm text-gray-700 italic">
                  &quot;No te decimos qué pensar. Te damos toda la información para que <strong>pienses por ti mismo</strong>.&quot;
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Call-to-action footer */}
        <div className="mt-20 text-center">
          <div className="inline-flex items-center space-x-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-full shadow-lg hover:shadow-xl transition-shadow">
            <span className="font-semibold">Información completa y equilibrada, en tu bandeja</span>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </div>
        </div>
      </div>
    </section>
  );
}
