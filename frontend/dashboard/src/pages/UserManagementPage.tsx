import React, { useEffect, useState } from 'react';
import { Shield, MoreVertical } from 'lucide-react';
import { toast } from 'react-hot-toast';
import clsx from 'clsx';
import { api } from '../services/api';
import { User } from '../types';

// SN-012g/§13.10: this page previously listed three hardcoded MOCK_USERS
// (one literally named after this project's own developer) with no API call
// anywhere in the file, and both the "Invite User" button and the per-row
// action button had no onClick handler — clicking did nothing. A real
// GET /users, PATCH /users/{id}/role and PATCH /users/{id}/status already
// exist (backend/app/api/users.py, wrapped in services/api.ts), so this now
// lists real users and the per-row menu performs a real status toggle.
// There is no admin-invite endpoint, so "Invite User" is left out rather
// than faked — registration is self-service (POST /auth/register).
const UserManagementPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const fetchUsers = async () => {
    try {
      const res = await api.users.getAll();
      setUsers(res.data);
    } catch (err) {
      toast.error('Could not load users from the backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleToggleActive = async (user: User) => {
    setOpenMenuId(null);
    try {
      await api.users.updateStatus(user.id, !user.is_active);
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_active: !u.is_active } : u));
      toast.success(`${user.name} ${!user.is_active ? 'activated' : 'deactivated'}.`);
    } catch (err) {
      toast.error(`Could not update status for ${user.name}.`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">User Management</h1>
          <div className="flex items-center gap-2 text-sm text-slate-500 mt-1">
            <Shield className="w-4 h-4 text-sky-600" />
            <span>Admin access only</span>
          </div>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-6 py-4 text-xs font-medium text-slate-500 uppercase tracking-wider">User</th>
                <th className="px-6 py-4 text-xs font-medium text-slate-500 uppercase tracking-wider">Role</th>
                <th className="px-6 py-4 text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-xs font-medium text-slate-500 uppercase tracking-wider">Joined</th>
                <th className="px-6 py-4 text-xs font-medium text-slate-500 uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {!loading && users.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-sm text-slate-400">
                    No users found.
                  </td>
                </tr>
              )}
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-full bg-sky-100 text-sky-700 flex items-center justify-center font-bold">
                        {user.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div>
                        <div className="font-semibold text-slate-800">{user.name}</div>
                        <div className="text-sm text-slate-500">{user.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={clsx(
                      "px-2.5 py-1 text-xs font-semibold rounded-full",
                      user.role === 'ADMIN' ? "bg-purple-100 text-purple-700" :
                      user.role === 'OPERATOR' ? "bg-blue-100 text-blue-700" :
                      "bg-slate-100 text-slate-700"
                    )}>
                      {user.role}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={clsx(
                      "px-2.5 py-1 text-xs font-semibold rounded-full",
                      user.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"
                    )}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right relative">
                    <button
                      onClick={() => setOpenMenuId(openMenuId === user.id ? null : user.id)}
                      className="p-2 text-slate-400 hover:text-sky-600 hover:bg-sky-50 rounded-lg transition-colors inline-flex"
                    >
                      <MoreVertical className="w-5 h-5" />
                    </button>
                    {openMenuId === user.id && (
                      <div className="absolute right-6 top-12 z-10 bg-white border border-slate-200 rounded-lg shadow-lg py-1 w-40 text-left">
                        <button
                          onClick={() => handleToggleActive(user)}
                          className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default UserManagementPage;
