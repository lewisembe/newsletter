'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { userApi } from '@/lib/api-client';

interface User {
  id: number;
  nombre: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export default function UsersManagement() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await userApi.getAllUsers(true);
      setUsers(response.data);
    } catch (err: any) {
      setError('Error al cargar usuarios');
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      await userApi.updateUserRole(userId, newRole);
      await fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al actualizar el rol');
    }
  };

  const handleDeactivate = async (userId: number, userName: string) => {
    if (!confirm(`¿Estás seguro de que quieres desactivar a ${userName}?`)) {
      return;
    }

    try {
      await userApi.deactivateUser(userId);
      await fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al desactivar usuario');
    }
  };

  const handleReactivate = async (userId: number, userName: string) => {
    if (!confirm(`¿Estás seguro de que quieres reactivar a ${userName}?`)) {
      return;
    }

    try {
      await userApi.reactivateUser(userId);
      await fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al reactivar usuario');
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8">Cargando usuarios...</div>;
  }

  return (
    <div>
      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Nombre
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Correo
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Rol
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Estado
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Acciones
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {users.map((user) => (
              <tr key={user.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {user.nombre}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {user.email}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {user.role === 'admin' ? (
                    <span className="capitalize font-semibold text-indigo-600">{user.role}</span>
                  ) : (
                    <select
                      value={user.role}
                      onChange={(e) => handleRoleChange(user.id, e.target.value)}
                      className="block w-full border-gray-300 rounded-md shadow-sm text-sm focus:ring-indigo-500 focus:border-indigo-500"
                      disabled={user.id === currentUser?.id}
                    >
                      <option value="user">Usuario</option>
                      <option value="enterprise">Empresa</option>
                    </select>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  <span
                    className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      user.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {user.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  {user.role !== 'admin' && user.id !== currentUser?.id && (
                    <>
                      {user.is_active ? (
                        <button
                          onClick={() => handleDeactivate(user.id, user.nombre)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Desactivar
                        </button>
                      ) : (
                        <button
                          onClick={() => handleReactivate(user.id, user.nombre)}
                          className="text-green-600 hover:text-green-900"
                        >
                          Reactivar
                        </button>
                      )}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
