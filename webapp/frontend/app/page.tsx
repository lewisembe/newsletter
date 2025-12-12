'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import Hero from "@/components/landing/Hero";
import Preview from "@/components/landing/Preview";
import ValueProps from "@/components/landing/ValueProps";
import Intelligence from "@/components/landing/Intelligence";
import Channels from "@/components/landing/Channels";
import Features from "@/components/landing/Features";
import CTA from "@/components/landing/CTA";
import Footer from "@/components/landing/Footer";

export default function Home() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    // Si el usuario está autenticado, redirigir al dashboard
    if (!loading && user) {
      router.push('/dashboard');
    }
  }, [user, loading, router]);

  // Mientras carga o si está autenticado (antes de redirigir), mostrar loading
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-purple-50">
        <div className="text-center">
          <div className="relative inline-block mb-8">
            <div className="absolute inset-0 animate-ping opacity-75">
              <svg
                className="w-24 h-24 text-indigo-400"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M9 12h6M9 16h6M13 4H7C5.89543 4 5 4.89543 5 6v12c0 1.1046.89543 2 2 2h10c1.1046 0 2-.8954 2-2V10l-6-6z"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <svg
              className="relative w-24 h-24 text-indigo-600 animate-pulse"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M9 12h6M9 16h6M13 4H7C5.89543 4 5 4.89543 5 6v12c0 1.1046.89543 2 2 2h10c1.1046 0 2-.8954 2-2V10l-6-6z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M13 4v6h6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h2 className="text-3xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-4">
            Briefy
          </h2>
          <p className="text-gray-600 text-lg">Cargando...</p>
        </div>
      </div>
    );
  }

  // Si está autenticado, no mostrar nada (se redirigirá)
  if (user) {
    return null;
  }

  // Si no está autenticado, mostrar landing page
  return (
    <main className="min-h-screen">
      <Hero />
      <Preview />
      <ValueProps />
      <Intelligence />
      <Channels />
      <Features />
      <CTA />
      <Footer />
    </main>
  );
}
