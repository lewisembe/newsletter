export default function Intelligence() {
  return (
    <section className="py-24 px-4 bg-gradient-to-b from-gray-50 via-white to-indigo-50 relative overflow-hidden">
      {/* Decoración de fondo */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-gradient-to-br from-indigo-200 to-purple-200 rounded-full blur-3xl opacity-20" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-gradient-to-br from-blue-200 to-cyan-200 rounded-full blur-3xl opacity-20" />

      <div className="max-w-7xl mx-auto relative z-10">
        {/* Header Principal */}
        <div className="text-center mb-20">
          <div className="inline-block mb-4 px-4 py-2 bg-gradient-to-r from-indigo-100 to-purple-100 rounded-full border border-indigo-200">
            <span className="text-indigo-700 text-sm font-semibold">🧠 INTELIGENCIA CONTEXTUAL</span>
          </div>
          <h2 className="text-5xl md:text-6xl font-black mb-6 text-gray-900 leading-tight">
            Más que noticias:
            <br />
            <span className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
              Comprensión total del mundo
            </span>
          </h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
            Nuestra IA conecta eventos, analiza tendencias y te explica el contexto
            que necesitas para <strong>entender realmente lo que está pasando</strong>.
          </p>
        </div>

        {/* Grid de beneficios principales */}
        <div className="grid md:grid-cols-3 gap-8 mb-20">
          {/* Contexto Completo */}
          <div className="bg-white rounded-2xl p-8 shadow-lg border border-gray-200 hover:shadow-2xl transition-all hover:-translate-y-1">
            <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center mb-6">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold mb-4 text-gray-900">
              Contexto Instantáneo
            </h3>
            <p className="text-gray-600 leading-relaxed mb-4">
              ¿Qué pasó antes? ¿Qué implica ahora? ¿Qué viene después?
              Te explicamos <strong>desde los fundamentos</strong> hasta las consecuencias.
            </p>
            <div className="flex items-center text-sm text-indigo-600 font-semibold">
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              Explicado desde cero
            </div>
          </div>

          {/* Perspectiva Completa */}
          <div className="bg-white rounded-2xl p-8 shadow-lg border border-gray-200 hover:shadow-2xl transition-all hover:-translate-y-1">
            <div className="w-14 h-14 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center mb-6">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold mb-4 text-gray-900">
              Conectando Eventos
            </h3>
            <p className="text-gray-600 leading-relaxed mb-4">
              Relacionamos automáticamente decisiones políticas, movimientos económicos
              y eventos sociales para darte <strong>la imagen completa</strong>.
            </p>
            <div className="flex items-center text-sm text-purple-600 font-semibold">
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 3.5a1.5 1.5 0 013 0V4a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-.5a1.5 1.5 0 000 3h.5a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-.5a1.5 1.5 0 00-3 0v.5a1 1 0 01-1 1H6a1 1 0 01-1-1v-3a1 1 0 00-1-1h-.5a1.5 1.5 0 010-3H4a1 1 0 001-1V6a1 1 0 011-1h3a1 1 0 001-1v-.5z" />
              </svg>
              Red de conocimiento
            </div>
          </div>

          {/* Tiempo Record */}
          <div className="bg-white rounded-2xl p-8 shadow-lg border border-gray-200 hover:shadow-2xl transition-all hover:-translate-y-1">
            <div className="w-14 h-14 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl flex items-center justify-center mb-6">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold mb-4 text-gray-900">
              5 Minutos, 50 Fuentes
            </h3>
            <p className="text-gray-600 leading-relaxed mb-4">
              Lo que te tomaría <strong>horas investigar</strong>, nuestra IA lo procesa
              en segundos. Información relevante, explicada, lista para ti.
            </p>
            <div className="flex items-center text-sm text-orange-600 font-semibold">
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" />
              </svg>
              Ultra rápido
            </div>
          </div>
        </div>

        {/* Sección "Cómo funciona la inteligencia" */}
        <div className="bg-gradient-to-br from-slate-900 via-indigo-900 to-purple-900 rounded-3xl p-12 mb-20 relative overflow-hidden shadow-2xl">
          {/* Patrón de fondo */}
          <div className="absolute inset-0 opacity-10" style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, white 1px, transparent 0)`,
            backgroundSize: '40px 40px'
          }} />

          <div className="relative z-10">
            <div className="text-center mb-12">
              <h3 className="text-4xl font-bold text-white mb-4">
                Cómo funciona la inteligencia
              </h3>
              <p className="text-xl text-indigo-200">
                Del caos informativo a conocimiento estructurado en 4 pasos
              </p>
            </div>

            <div className="grid md:grid-cols-4 gap-6">
              {/* Paso 1 */}
              <div className="relative">
                <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20 h-full">
                  <div className="text-5xl font-black text-indigo-400 mb-4">01</div>
                  <h4 className="text-xl font-bold text-white mb-3">Recolección</h4>
                  <p className="text-indigo-200 text-sm leading-relaxed">
                    Monitoreamos 50+ fuentes en tiempo real, capturando noticias de economía, política, tecnología y más
                  </p>
                </div>
                {/* Flecha conectora (desktop) */}
                <div className="hidden md:block absolute top-1/2 -right-3 transform -translate-y-1/2">
                  <svg className="w-6 h-6 text-indigo-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M12.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>

              {/* Paso 2 */}
              <div className="relative">
                <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20 h-full">
                  <div className="text-5xl font-black text-purple-400 mb-4">02</div>
                  <h4 className="text-xl font-bold text-white mb-3">Análisis Semántico</h4>
                  <p className="text-indigo-200 text-sm leading-relaxed">
                    IA detecta temas, relaciona eventos y agrupa historias conectadas. Identifica causas y consecuencias
                  </p>
                </div>
                <div className="hidden md:block absolute top-1/2 -right-3 transform -translate-y-1/2">
                  <svg className="w-6 h-6 text-purple-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M12.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>

              {/* Paso 3 */}
              <div className="relative">
                <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20 h-full">
                  <div className="text-5xl font-black text-pink-400 mb-4">03</div>
                  <h4 className="text-xl font-bold text-white mb-3">Contextualización</h4>
                  <p className="text-indigo-200 text-sm leading-relaxed">
                    Añadimos antecedentes, explicamos conceptos clave y mostramos el panorama completo
                  </p>
                </div>
                <div className="hidden md:block absolute top-1/2 -right-3 transform -translate-y-1/2">
                  <svg className="w-6 h-6 text-pink-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M12.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>

              {/* Paso 4 */}
              <div>
                <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20 h-full">
                  <div className="text-5xl font-black text-cyan-400 mb-4">04</div>
                  <h4 className="text-xl font-bold text-white mb-3">Personalización</h4>
                  <p className="text-indigo-200 text-sm leading-relaxed">
                    Priorizamos lo relevante para ti, eliminamos ruido y entregamos tu newsletter personalizada
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Sección "Para todos" */}
        <div className="grid md:grid-cols-2 gap-12 items-center mb-20">
          {/* Contenido */}
          <div>
            <div className="inline-block mb-4 px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-semibold">
              🚀 ACCESIBLE PARA TODOS
            </div>
            <h3 className="text-4xl font-bold mb-6 text-gray-900">
              Automatizado, escalable y económico
            </h3>
            <p className="text-lg text-gray-700 mb-6 leading-relaxed">
              Ya seas una persona curiosa, un profesional ocupado o una organización completa,
              nuestro sistema se adapta a ti. <strong>Sin fricciones, sin costes prohibitivos</strong>.
            </p>

            <div className="space-y-6">
              <div className="flex items-start">
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-500 rounded-xl flex items-center justify-center text-white text-2xl mr-4">
                  👤
                </div>
                <div>
                  <h4 className="text-lg font-bold text-gray-900 mb-1">Para Individuos</h4>
                  <p className="text-gray-600">
                    Mantente informado sin dedicar horas. Instala, configura y recibe tu newsletter personalizado gratis.
                  </p>
                </div>
              </div>

              <div className="flex items-start">
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center text-white text-2xl mr-4">
                  💼
                </div>
                <div>
                  <h4 className="text-lg font-bold text-gray-900 mb-1">Para Profesionales</h4>
                  <p className="text-gray-600">
                    Filtra por tu sector, competencia o áreas de interés. Información estratégica sin costes de suscripción.
                  </p>
                </div>
              </div>

              <div className="flex items-start">
                <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center text-white text-2xl mr-4">
                  🏢
                </div>
                <div>
                  <h4 className="text-lg font-bold text-gray-900 mb-1">Para Organizaciones</h4>
                  <p className="text-gray-600">
                    Inteligencia competitiva automatizada. Despliega para toda tu organización, self-hosted y personalizable.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Visual: Free Model */}
          <div>
            <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-2xl shadow-2xl p-8 border-2 border-green-400 relative overflow-hidden">
              {/* Badge "FREE" flotante */}
              <div className="absolute -top-4 -right-4 w-32 h-32 bg-gradient-to-br from-green-500 to-emerald-500 rounded-full opacity-20 blur-2xl"></div>

              <div className="relative z-10">
                <div className="text-center mb-8">
                  <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-green-500 to-emerald-500 rounded-full mb-4 shadow-xl">
                    <svg className="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v2H7a1 1 0 100 2h2v2a1 1 0 102 0v-2h2a1 1 0 100-2h-2V7z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <h4 className="text-3xl font-black text-gray-900 mb-2">
                    100% GRATIS
                  </h4>
                  <p className="text-green-700 font-semibold text-lg">
                    Acceso sin coste para todos
                  </p>
                </div>

                <div className="space-y-4 mb-6">
                  <div className="flex items-start bg-white/50 rounded-lg p-4">
                    <div className="flex-shrink-0 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center mr-3 mt-0.5">
                      <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div>
                      <div className="font-bold text-gray-900 mb-1">Usuarios: Newsletters públicas gratis</div>
                      <div className="text-sm text-gray-600">Accede a newsletters curadas sin coste alguno</div>
                    </div>
                  </div>

                  <div className="flex items-start bg-white/50 rounded-lg p-4">
                    <div className="flex-shrink-0 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center mr-3 mt-0.5">
                      <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div>
                      <div className="font-bold text-gray-900 mb-1">Enterprise: Personaliza con tu API key</div>
                      <div className="text-sm text-gray-600">Usa tu propia clave de OpenAI y personaliza totalmente (~$0.05/día)</div>
                    </div>
                  </div>

                  <div className="flex items-start bg-white/50 rounded-lg p-4">
                    <div className="flex-shrink-0 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center mr-3 mt-0.5">
                      <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div>
                      <div className="font-bold text-gray-900 mb-1">Sin suscripciones ni pagos mensuales</div>
                      <div className="text-sm text-gray-600">No tarjeta de crédito, no compromisos</div>
                    </div>
                  </div>
                </div>

                <div className="bg-gradient-to-r from-green-600 to-emerald-600 rounded-lg p-4 text-center">
                  <div className="flex items-center justify-center space-x-2 text-white">
                    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M3 5a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2h-2.22l.123.489.804.804A1 1 0 0113 18H7a1 1 0 01-.707-1.707l.804-.804L7.22 15H5a2 2 0 01-2-2V5zm5.771 7H5V5h10v7H8.771z" clipRule="evenodd" />
                    </svg>
                    <span className="font-bold text-lg">Para todos</span>
                  </div>
                  <p className="text-green-100 text-sm mt-2">
                    Lee newsletters públicas gratis o crea las tuyas con tu API
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* CTA Final */}
        <div className="text-center bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 rounded-3xl p-12 text-white relative overflow-hidden">
          <div className="absolute inset-0 opacity-20" style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
          }} />

          <div className="relative z-10">
            <h3 className="text-4xl font-black mb-4">
              Inteligencia artificial al servicio de tu conocimiento
            </h3>
            <p className="text-xl text-indigo-100 mb-8 max-w-2xl mx-auto">
              Deja que la tecnología haga el trabajo pesado. Tú solo disfruta de estar informado.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="#cta"
                className="inline-flex items-center justify-center px-8 py-4 bg-white text-indigo-600 rounded-full font-bold text-lg hover:bg-gray-100 transition-all shadow-xl hover:shadow-2xl hover:scale-105"
              >
                Empezar Gratis
                <svg className="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </a>
              <a
                href="#features"
                className="inline-flex items-center justify-center px-8 py-4 border-2 border-white text-white rounded-full font-bold text-lg hover:bg-white/10 transition-all"
              >
                Ver Cómo Funciona
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
