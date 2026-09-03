import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

const DashboardLayout: React.FC = () => {
  return (
    <div className="flex h-screen bg-surface-secondary overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <Header />
        <main className="flex-1 overflow-x-hidden overflow-y-auto bg-surface-secondary">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;
