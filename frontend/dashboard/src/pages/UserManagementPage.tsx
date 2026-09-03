import React from 'react';
import { Shield, Plus, MoreVertical } from 'lucide-react';
import clsx from 'clsx';

type Role = 'ADMIN' | 'OPERATOR' | 'VIEWER';
type Status = 'Active' | 'Inactive';

interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  status: Status;
  joined: string;
}

const MOCK_USERS: User[] = [
  { id: '1', name: 'Alok Sharma', email: 'alok.s@surakshanet.in', role: 'ADMIN', status: 'Active', joined: 'Oct 12, 2025' },
  { id: '2', name: 'Priya Singh', email: 'priya.singh@surakshanet.in', role: 'OPERATOR', status: 'Active', joined: 'Nov 04, 2025' },
  { id: '3', name: 'Rahul Verma', email: 'rahul.v@surakshanet.in', role: 'VIEWER', status: 'Inactive', joined: 'Dec 15, 2025' },
];

const UserManagementPage: React.FC = () => {
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
        <button className="flex items-center gap-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg px-4 py-2.5 font-medium transition-colors shadow-sm">
          <Plus className="w-5 h-5" />
          <span>Invite User</span>
        </button>
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
              {MOCK_USERS.map((user) => (
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
                      user.status === 'Active' ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"
                    )}>
                      {user.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {user.joined}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="p-2 text-slate-400 hover:text-sky-600 hover:bg-sky-50 rounded-lg transition-colors inline-flex">
                      <MoreVertical className="w-5 h-5" />
                    </button>
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
