'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';

export default function ProfilePage() {
  const { user, updateProfile, deleteAccount } = useAuth();
  const [nombre, setNombre] = useState(user?.nombre || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // Separate error/success states for each form
  const [nameError, setNameError] = useState('');
  const [nameSuccess, setNameSuccess] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleteError, setDeleteError] = useState('');

  const [loading, setLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  if (!user) return null;

  const handleUpdateName = async (e: React.FormEvent) => {
    e.preventDefault();
    setNameError('');
    setNameSuccess('');
    setLoading(true);

    try {
      await updateProfile({ nombre });
      setNameSuccess('Nombre actualizado exitosamente');
    } catch (err: any) {
      setNameError(err.response?.data?.detail || 'Error al actualizar el nombre');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError('');
    setPasswordSuccess('');

    if (newPassword !== confirmPassword) {
      setPasswordError('Las contraseñas no coinciden');
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError('La contraseña debe tener al menos 8 caracteres');
      return;
    }

    setLoading(true);

    try {
      await updateProfile({ current_password: currentPassword, new_password: newPassword });
      setPasswordSuccess('Contraseña actualizada exitosamente');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPasswordError(err.response?.data?.detail || 'Error al actualizar la contraseña');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setDeleteError('');

    if (deleteConfirmation.trim().toLowerCase() !== user.email.trim().toLowerCase()) {
      setDeleteError('Debes escribir tu correo completo para confirmar.');
      return;
    }

    setDeleteLoading(true);
    try {
      await deleteAccount();
    } catch (err: any) {
      setDeleteError(err.response?.data?.detail || 'Error al eliminar la cuenta');
      setDeleteLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Configuración de Perfil</h1>

      <div className="space-y-8">
        {/* User Info */}
        <div className="bg-white shadow sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Información de Usuario</h3>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-sm font-medium text-gray-500">Correo</dt>
                <dd className="mt-1 text-sm text-gray-900">{user.email}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Rol</dt>
                <dd className="mt-1 text-sm text-gray-900 capitalize">{user.role}</dd>
              </div>
            </dl>
          </div>
        </div>

        {/* Update Name */}
        <div className="bg-white shadow sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Actualizar Nombre</h3>
            <form onSubmit={handleUpdateName} className="space-y-4">
              {nameError && (
                <div className="rounded-md bg-red-50 p-4">
                  <p className="text-sm text-red-700">{nameError}</p>
                </div>
              )}

              {nameSuccess && (
                <div className="rounded-md bg-green-50 p-4">
                  <p className="text-sm text-green-700">{nameSuccess}</p>
                </div>
              )}

              <div>
                <label htmlFor="nombre" className="block text-sm font-medium text-gray-700">
                  Nombre
                </label>
                <input
                  type="text"
                  id="nombre"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                Actualizar Nombre
              </button>
            </form>
          </div>
        </div>

        {/* Change Password */}
        <div className="bg-white shadow sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Cambiar Contraseña</h3>
            <form onSubmit={handleUpdatePassword} className="space-y-4">
              {passwordError && (
                <div className="rounded-md bg-red-50 p-4">
                  <p className="text-sm text-red-700">{passwordError}</p>
                </div>
              )}

              {passwordSuccess && (
                <div className="rounded-md bg-green-50 p-4">
                  <p className="text-sm text-green-700">{passwordSuccess}</p>
                </div>
              )}

              <div>
                <label htmlFor="currentPassword" className="block text-sm font-medium text-gray-700">
                  Contraseña Actual
                </label>
                <input
                  type="password"
                  id="currentPassword"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  required
                />
              </div>
              <div>
                <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700">
                  Nueva Contraseña
                </label>
                <input
                  type="password"
                  id="newPassword"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  required
                />
              </div>
              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700">
                  Confirmar Nueva Contraseña
                </label>
                <input
                  type="password"
                  id="confirmPassword"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                Cambiar Contraseña
              </button>
            </form>
          </div>
        </div>

        {/* Delete Account */}
        <div className="bg-white shadow sm:rounded-lg border border-red-100">
          <div className="px-4 py-5 sm:p-6">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <span className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-red-100 text-red-600">
                  <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M8.257 3.099c.765-1.36 2.721-1.36 3.486 0l5.58 9.92C18.09 14.7 17.126 16 15.837 16H4.163c-1.289 0-2.253-1.3-1.486-2.98l5.58-9.92zM11 14a1 1 0 10-2 0 1 1 0 002 0zm-1-2a1 1 0 01-1-1V8a1 1 0 112 0v3a1 1 0 01-1 1z"
                      clipRule="evenodd"
                    />
                  </svg>
                </span>
              </div>
              <div className="ml-4 w-full">
                <h3 className="text-lg font-medium text-gray-900">Eliminar Cuenta</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Esta acción desactivará tu cuenta y cerrarás sesión de inmediato. Si deseas regresar más tarde,
                  contacta con un administrador.
                </p>

                {deleteError && (
                  <div className="mt-4 rounded-md bg-red-50 p-4">
                    <p className="text-sm text-red-700">{deleteError}</p>
                  </div>
                )}

                <div className="mt-4 space-y-4">
                  {!showDeleteConfirm && (
                    <button
                      type="button"
                      onClick={() => setShowDeleteConfirm(true)}
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                    >
                      Eliminar cuenta
                    </button>
                  )}

                  {showDeleteConfirm && (
                    <form onSubmit={handleDeleteAccount} className="space-y-4">
                      <div>
                        <label htmlFor="deleteConfirmation" className="block text-sm font-medium text-gray-700">
                          Escribe tu correo ({user.email}) para confirmar
                        </label>
                        <input
                          type="text"
                          id="deleteConfirmation"
                          value={deleteConfirmation}
                          onChange={(e) => setDeleteConfirmation(e.target.value)}
                          className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm"
                          placeholder={user.email}
                        />
                      </div>
                      <div className="flex flex-wrap gap-3">
                        <button
                          type="submit"
                          disabled={deleteLoading}
                          className="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                        >
                          Confirmar y eliminar
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setShowDeleteConfirm(false);
                            setDeleteConfirmation('');
                            setDeleteError('');
                          }}
                          className="inline-flex justify-center py-2 px-4 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-400"
                        >
                          Cancelar
                        </button>
                      </div>
                      <p className="text-xs text-gray-500">
                        Esta acción es irreversible. Tu perfil quedará inactivo y no podrás iniciar sesión.
                      </p>
                    </form>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
