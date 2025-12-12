import { Mail, Github } from 'lucide-react';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="mt-auto border-t border-gray-100 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-3">
          {/* Brand Section */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-gray-900">Newsletter Hub</h3>
            <p className="text-sm text-gray-600">
              Tu fuente centralizada de noticias curadas por IA. Mantente informado con las historias más relevantes.
            </p>
          </div>

          {/* Links Section */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-gray-900">Enlaces</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="/dashboard" className="text-gray-600 hover:text-indigo-600 transition-colors">
                  Dashboard
                </a>
              </li>
              <li>
                <a href="/explore" className="text-gray-600 hover:text-indigo-600 transition-colors">
                  Explorar
                </a>
              </li>
              <li>
                <a href="/admin" className="text-gray-600 hover:text-indigo-600 transition-colors">
                  Admin
                </a>
              </li>
            </ul>
          </div>

          {/* Contact Section */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-gray-900">Contacto</h3>
            <div className="flex items-center gap-4">
              <a
                href="mailto:info@newsletter.com"
                className="text-gray-600 hover:text-indigo-600 transition-colors"
                aria-label="Email"
              >
                <Mail className="w-5 h-5" />
              </a>
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-600 hover:text-indigo-600 transition-colors"
                aria-label="GitHub"
              >
                <Github className="w-5 h-5" />
              </a>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-8 border-t border-gray-100 pt-6">
          <div className="flex flex-col items-center justify-center gap-4 text-sm text-gray-600">
            <p>
              © {currentYear} Newsletter Hub. Todos los derechos reservados.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
