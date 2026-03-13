"use client";

import { Menu, PanelLeftClose, PanelRightClose, PanelRight } from "lucide-react";

interface NavbarProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  driveOpen: boolean;
  onToggleDrive: () => void;
}

export function Navbar({ sidebarOpen, onToggleSidebar, driveOpen, onToggleDrive }: NavbarProps) {
  return (
    <header className="h-11 flex items-center px-3 shrink-0">
      <button
        onClick={onToggleSidebar}
        className="p-2 rounded-lg hover:bg-[var(--color-card)] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] transition-colors cursor-pointer"
        title={sidebarOpen ? "Close sidebar" : "Open sidebar"}
      >
        {sidebarOpen ? (
          <PanelLeftClose className="w-5 h-5" />
        ) : (
          <Menu className="w-5 h-5" />
        )}
      </button>

      <div className="flex-1 flex items-center justify-center">
        <span className="text-sm font-medium text-[var(--color-text-secondary)]">Archon</span>
      </div>

      <button
        onClick={onToggleDrive}
        className="p-2 rounded-lg hover:bg-[var(--color-card)] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] transition-colors cursor-pointer"
        title={driveOpen ? "Close drive panel" : "Open drive panel"}
      >
        {driveOpen ? (
          <PanelRightClose className="w-5 h-5" />
        ) : (
          <PanelRight className="w-5 h-5" />
        )}
      </button>
    </header>
  );
}
